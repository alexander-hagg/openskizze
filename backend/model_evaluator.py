#!/usr/bin/env python3
# OpenSKIZZE - U-Net Model Evaluator for GUI Integration
# Copyright (C) 2025 [Alexander Hagg]
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
U-Net Evaluator for Building Layout Assessment

Evaluates building layouts using a U-Net neural network trained on KLAM_21
cold-air drainage simulations.

Model Files:
- U-Net weights: models/unet_{SIZE}m.pth (e.g., unet_60m.pth)
- Normalization: models/unet_{SIZE}m_normalization.json

Usage:
    from model_evaluator import create_evaluator

    evaluator = create_evaluator(
        model_type='unet',
        parcel_size=60,
        device='cpu'
    )
    results = evaluator.evaluate(genomes, parcel_sizes)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import torch

from backend.unet import UNet, UNetConfig
from backend.fast_encoding import NumbaFastEncoding

logger = logging.getLogger(__name__)


# ============================================================================
# Model Size Mapping
# ============================================================================

def get_nearest_model_size(parcel_size: int) -> int:
    """
    Map any parcel size to nearest available U-Net model size.
    
    Available models: 60m, 120m, 240m (training in progress)
    Uses nearest neighbor mapping for best accuracy.
    
    Args:
        parcel_size: Actual parcel size in meters
    
    Returns:
        model_size: Nearest model size (60, 120, or 240)
    
    Examples:
        >>> get_nearest_model_size(51)  # Returns 60
        >>> get_nearest_model_size(81)  # Returns 60
        >>> get_nearest_model_size(90)  # Returns 120
        >>> get_nearest_model_size(180) # Returns 120
        >>> get_nearest_model_size(210) # Returns 240
    """
    model_sizes = [60, 120, 240]
    distances = [abs(parcel_size - size) for size in model_sizes]
    nearest_idx = distances.index(min(distances))
    return model_sizes[nearest_idx]


# ============================================================================
# Domain Grid Construction (for U-Net)
# ============================================================================

def construct_domain_grids_batch(
    heightmaps: np.ndarray,
    parcel_size_m: int,
    xy_scale: float = 3.0,
    environment_xy_size: int = 200
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorized construction of KLAM domain grids for U-Net input.
    
    Dynamically computes grid dimensions based on parcel size, matching
    the logic in evaluation_klam.py:
    - Domain extends 100% to left (upwind) for cold air source
    - Grid size scales with parcel size
    - 60m → 66×89, 120m → 120×160, 240m → 240×320
    
    Args:
        heightmaps: (N, D, D) building heights in meters
        parcel_size_m: Parcel size in meters (e.g., 60, 120, 240)
        xy_scale: Meters per cell (default 3.0)
        environment_xy_size: Minimum environment size in meters (default 200)
    
    Returns:
        terrain: (N, grid_h, grid_w) elevation in meters
        buildings: (N, grid_h, grid_w) building heights in meters
        landuse: (N, grid_h, grid_w) landuse codes
    """
    N = len(heightmaps)
    
    # Calculate grid dimensions (matches evaluation_klam.py logic)
    parcel_size_cells = int(parcel_size_m / xy_scale)
    env_size_m = max(environment_xy_size, parcel_size_m * 3)
    env_cells_base = int(env_size_m / xy_scale)
    original_offset = (env_cells_base - parcel_size_cells) // 2
    left_extension = original_offset  # 100% more space to left
    
    grid_h = env_cells_base  # Height (y)
    grid_w = env_cells_base + left_extension  # Width (x) with extension
    
    # Initialize grids
    terrain = np.zeros((N, grid_h, grid_w), dtype=np.float32)
    buildings = np.zeros((N, grid_h, grid_w), dtype=np.float32)
    landuse = np.full((N, grid_h, grid_w), 2, dtype=np.int8)  # Low-density default
    
    # Terrain: 2° slope upwind (left half) - matches KLAM physics update
    slope_end_col = grid_w // 2
    for col in range(slope_end_col):
        terrain[:, :, col] = (slope_end_col - col) * xy_scale * np.tan(np.radians(2.0))
    
    # Place buildings in center (shifted right due to left extension)
    offset_x = original_offset + left_extension
    offset_y = original_offset
    buildings[:, offset_y:offset_y+parcel_size_cells, offset_x:offset_x+parcel_size_cells] = heightmaps
    
    # Landuse: 7 (free space) in upwind half
    landuse[:, :, :slope_end_col] = 7
    
    return terrain, buildings, landuse


# ============================================================================
# U-Net Evaluator
# ============================================================================

class UNetEvaluator:
    """Evaluator using U-Net model (highest accuracy)."""
    
    def __init__(
        self,
        model_path: Path,
        parcel_size: int,
        device: torch.device,
        actual_parcel_size: Optional[int] = None
    ):
        self.device = device
        self.parcel_size = parcel_size  # Model size (e.g., 81m)
        self.parcel_size_cells = parcel_size // 3  # Model size in cells (e.g., 27)
        
        # Actual parcel size may be smaller (e.g., 51m actual vs 81m model)
        self.actual_parcel_size = actual_parcel_size if actual_parcel_size else parcel_size
        self.actual_parcel_size_cells = self.actual_parcel_size // 3
        
        logger.info(f"Loading U-Net model from {model_path}")
        logger.info(f"  Model size: {parcel_size}m ({self.parcel_size_cells} cells)")
        logger.info(f"  Actual parcel size: {self.actual_parcel_size}m ({self.actual_parcel_size_cells} cells)")
        
        # Load model
        checkpoint = torch.load(model_path, map_location=device, weights_only=False)
        config = UNetConfig(**checkpoint['config'])
        
        self.model = UNet(config).to(device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        
        # FP16 optimization on GPU
        if device.type == 'cuda':
            self.model = self.model.half()
            logger.info("  ✓ FP16 enabled")
        
        # Load normalization stats from size-specific U-Net file
        # Extract parcel size from model filename (e.g., unet_81m.pth -> 81m)
        model_filename = model_path.stem  # e.g., 'unet_81m'
        parcel_size_str = model_filename.replace('unet_', '')  # e.g., '81m'
        norm_path = model_path.parent / f'unet_{parcel_size_str}_normalization.json'
        with open(norm_path) as f:
            norm_stats = json.load(f)
        
        # Handle both flat and nested normalization formats
        if 'input' in norm_stats and 'output' in norm_stats:
            # Nested format: {"input": {"terrain": {"mean": ..., "std": ...}}, "output": {...}}
            self.terrain_mean = norm_stats['input']['terrain']['mean']
            self.terrain_std = norm_stats['input']['terrain']['std']
            self.buildings_mean = norm_stats['input']['buildings']['mean']
            self.buildings_std = norm_stats['input']['buildings']['std']
            self.landuse_mean = norm_stats['input']['landuse']['mean']
            self.landuse_std = norm_stats['input']['landuse']['std']
            
            # Output normalization
            self.ex_mean = norm_stats['output']['Ex']['mean']
            self.ex_std = norm_stats['output']['Ex']['std']
            self.hx_mean = norm_stats['output'].get('Hx', {}).get('mean', 0.0)
            self.hx_std = norm_stats['output'].get('Hx', {}).get('std', 1.0)
            self.uq_mean = norm_stats['output']['uq']['mean']
            self.uq_std = norm_stats['output']['uq']['std']
            self.vq_mean = norm_stats['output']['vq']['mean']
            self.vq_std = norm_stats['output']['vq']['std']
            self.uz_mean = norm_stats['output'].get('uz', {}).get('mean', 0.0)
            self.uz_std = norm_stats['output'].get('uz', {}).get('std', 1.0)
            self.vz_mean = norm_stats['output'].get('vz', {}).get('mean', 0.0)
            self.vz_std = norm_stats['output'].get('vz', {}).get('std', 1.0)
        else:
            # Flat format: {"terrain_mean": ..., "terrain_std": ..., ...}
            self.terrain_mean = norm_stats['terrain_mean']
            self.terrain_std = norm_stats['terrain_std']
            self.buildings_mean = norm_stats['buildings_mean']
            self.buildings_std = norm_stats['buildings_std']
            self.landuse_mean = norm_stats['landuse_mean']
            self.landuse_std = norm_stats['landuse_std']
            
            self.uq_mean = norm_stats['uq_mean']
            self.uq_std = norm_stats['uq_std']
            self.vq_mean = norm_stats['vq_mean']
            self.vq_std = norm_stats['vq_std']
            self.uz_mean = norm_stats.get('uz_mean', 0.0)
            self.uz_std = norm_stats.get('uz_std', 1.0)
            self.vz_mean = norm_stats.get('vz_mean', 0.0)
            self.vz_std = norm_stats.get('vz_std', 1.0)
            self.ex_mean = norm_stats['ex_mean']
            self.ex_std = norm_stats['ex_std']
            self.hx_mean = norm_stats.get('hx_mean', 0.0)
            self.hx_std = norm_stats.get('hx_std', 1.0)
        
        # Initialize fast encoding (uses ACTUAL parcel size, not model size)
        self.fast_encoding = NumbaFastEncoding(parcel_size=self.actual_parcel_size)
        
        # Calculate grid dimensions (must match training data)
        xy_scale = 3.0
        environment_xy_size = 200
        env_size_m = max(environment_xy_size, parcel_size * 3)
        env_cells_base = int(env_size_m / xy_scale)
        original_offset = (env_cells_base - self.parcel_size_cells) // 2
        left_extension = original_offset
        
        self.grid_h = env_cells_base
        self.grid_w = env_cells_base + left_extension
        
        # ROI mask (region of interest on ACTUAL parcel, not padded model area)
        offset_x = original_offset + left_extension
        offset_y = original_offset
        # Account for zero-padding offset (actual parcel centered in model parcel)
        pad_offset = (self.parcel_size_cells - self.actual_parcel_size_cells) // 2
        self.roi_mask = np.zeros((self.grid_h, self.grid_w), dtype=bool)
        self.roi_mask[
            offset_y + pad_offset:offset_y + pad_offset + self.actual_parcel_size_cells,
            offset_x + pad_offset:offset_x + pad_offset + self.actual_parcel_size_cells
        ] = True
        
        logger.info(f"U-Net loaded successfully (grid: {self.grid_h}×{self.grid_w})")
    
    def evaluate(
        self,
        genomes: np.ndarray,
        parcel_sizes: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Evaluate genomes using U-Net.
        
        Args:
            genomes: (N, 60) genome array
            parcel_sizes: (N,) parcel sizes in meters
        
        Returns:
            Dictionary with:
            - objectives: Cold air flux predictions
            - features: (N, 8) planning features
        """
        # Express genomes to heightmaps
        heightmaps = self.fast_encoding.express_batch(genomes)
        
        # Compute features for archive
        from backend.fast_encoding import numba_calculate_features
        pixel_size = self.fast_encoding.config['xy_scale']
        N = len(genomes)
        features = np.zeros((N, 8), dtype=np.float64)
        for i in range(N):
            features[i] = numba_calculate_features(heightmaps[i], pixel_size)
        
        # Zero-pad heightmaps if actual parcel is smaller than model parcel
        D = heightmaps.shape[1]  # actual_parcel_size_cells
        P = self.parcel_size_cells  # model parcel size in cells (e.g. 20 for 60m)
        if D < P:
            padded = np.zeros((N, P, P), dtype=heightmaps.dtype)
            offset = (P - D) // 2
            padded[:, offset:offset+D, offset:offset+D] = heightmaps
            heightmaps = padded
        
        # Construct domain grids with dynamic sizing
        terrain, buildings, landuse = construct_domain_grids_batch(
            heightmaps,
            self.parcel_size  # Pass parcel size in meters
        )
        
        # Normalize inputs
        terrain_norm = (terrain - self.terrain_mean) / self.terrain_std
        buildings_norm = (buildings - self.buildings_mean) / self.buildings_std
        landuse_norm = (landuse - self.landuse_mean) / self.landuse_std
        
        # Stack: (N, 3, H, W)
        X = np.stack([terrain_norm, buildings_norm, landuse_norm], axis=1)
        
        # Convert to tensor
        dtype = torch.float16 if self.device.type == 'cuda' else torch.float32
        X_torch = torch.tensor(X, dtype=dtype, device=self.device)
        
        # Predict
        with torch.no_grad():
            Y_pred = self.model(X_torch)
        
        # Denormalize outputs using scalar mean/std
        # Y_pred shape: (N, 6, H, W) - [Ex, Hx, uq, vq, uz, vz]
        Y_pred = Y_pred.float().cpu().numpy()
        Ex = Y_pred[:, 0, :, :] * self.ex_std + self.ex_mean
        uq = Y_pred[:, 2, :, :] * self.uq_std + self.uq_mean
        vq = Y_pred[:, 3, :, :] * self.vq_std + self.vq_mean
        
        # Compute cold air flux: Φ = mean(Ex) * mean(sqrt(uq^2 + vq^2))
        # Convert cm/s → m/s
        uq_ms = uq / 100.0
        vq_ms = vq / 100.0
        
        # Apply ROI mask and compute means
        Ex_roi = np.where(self.roi_mask, Ex, 0)
        uq_roi = np.where(self.roi_mask, uq_ms, 0)
        vq_roi = np.where(self.roi_mask, vq_ms, 0)
        
        roi_count = self.roi_mask.sum()
        Ex_mean = Ex_roi.sum(axis=(1,2)) / roi_count
        wind_speed = np.sqrt(uq_roi**2 + vq_roi**2).sum(axis=(1,2)) / roi_count
        
        objectives = Ex_mean * wind_speed  # Cold air flux
        
        return {
            'objectives': objectives,
            'features': features
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_evaluator(
    model_type: str,
    parcel_size: int,
    models_dir: Path = Path('models'),
    device: str = 'cpu',
    actual_parcel_size: Optional[int] = None,
    **kwargs
):
    """
    Create a U-Net evaluator.
    
    Args:
        model_type: Must be 'unet'
        parcel_size: Model parcel size in meters (e.g., 60)
        models_dir: Directory containing model files
        device: 'cuda' or 'cpu'
        actual_parcel_size: Actual parcel size in meters (may be smaller)
    
    Returns:
        UNetEvaluator instance
    """
    device = torch.device(device)
    unet_path = models_dir / f'unet_{parcel_size}m.pth'
    
    if model_type != 'unet':
        raise ValueError(f"Only 'unet' model type is supported, got '{model_type}'")
    
    if not unet_path.exists():
        raise FileNotFoundError(f"U-Net model not found: {unet_path}")
    
    return UNetEvaluator(unet_path, parcel_size, device, actual_parcel_size)
