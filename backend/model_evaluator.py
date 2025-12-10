#!/usr/bin/env python3
# OpenSKIZZE - Unified Model Evaluator for GUI Integration
# Copyright (C) 2025 [Alexander Hagg]
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Unified Evaluator for SVGP, U-Net, and Hybrid Models

This module provides a single interface for evaluating building layouts using:
1. SVGP model (fast, provides uncertainty, works for ALL parcel sizes)
2. U-Net model (most accurate, no uncertainty, size-specific)
3. Hybrid model (U-Net fitness + SVGP uncertainty for exploration)

Model Files:
- SVGP: models/svgp.pth (single model, parcel size as input)
- U-Net: models/unet_{SIZE}m.pth (size-specific, e.g., unet_81m.pth)
- U-Net normalization: models/unet_{SIZE}m_normalization.json

All evaluators use the optimized fast_encoding.py for consistent feature
calculation and performance.

Usage:
    from model_evaluator import create_evaluator
    
    # Create evaluator (parcel_size in meters, e.g., 81m)
    evaluator = create_evaluator(
        model_type='hybrid',  # or 'svgp' or 'unet'
        parcel_size=81,  # Parcel size in meters
        device='cuda',
        ucb_lambda=1.0  # For UCB exploration
    )
    
    # Evaluate batch of genomes
    results = evaluator.evaluate(genomes, parcel_sizes)
    objectives = results['objectives']
    uncertainties = results.get('uncertainties', None)  # Only for SVGP/Hybrid
"""

import json
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional

import numpy as np
import torch
import gpytorch

from backend.svgp import SVGPModel, load_svgp_model
from backend.unet import UNet, UNetConfig
from backend.fast_encoding import NumbaFastEncoding

logger = logging.getLogger(__name__)


# ============================================================================
# Domain Grid Construction (for U-Net)
# ============================================================================

def construct_domain_grids_batch(
    heightmaps: np.ndarray,
    parcel_size_cells: int,
    grid_h: int = 66,
    grid_w: int = 94
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorized construction of KLAM domain grids for U-Net input.
    
    Creates 66×94 simulation domains with:
    - 1° sloped terrain upwind (cold air source)
    - Building heightmaps centered
    - Landuse: 7 (free space) upwind, 2 (low-density) elsewhere
    
    Args:
        heightmaps: (N, D, D) building heights in meters
        parcel_size_cells: Parcel size in cells (e.g., 9 for 27m at 3m/cell)
        grid_h: Domain height (default 66)
        grid_w: Domain width (default 94)
    
    Returns:
        terrain: (N, grid_h, grid_w) elevation in meters
        buildings: (N, grid_h, grid_w) building heights in meters
        landuse: (N, grid_h, grid_w) landuse codes
    """
    N = len(heightmaps)
    
    # Initialize grids
    terrain = np.zeros((N, grid_h, grid_w), dtype=np.float32)
    buildings = np.zeros((N, grid_h, grid_w), dtype=np.float32)
    landuse = np.full((N, grid_h, grid_w), 2, dtype=np.int8)  # Low-density default
    
    # Terrain: 1° slope upwind (left half)
    slope_end_col = grid_w // 2
    for col in range(slope_end_col):
        terrain[:, :, col] = (slope_end_col - col) * 3.0 * np.tan(np.radians(1.0))
    
    # Place buildings in center
    start_row = (grid_h - parcel_size_cells) // 2
    start_col = (grid_w - parcel_size_cells) // 2
    buildings[:, start_row:start_row+parcel_size_cells, start_col:start_col+parcel_size_cells] = heightmaps
    
    # Landuse: 7 (free space) in upwind half
    landuse[:, :, :slope_end_col] = 7
    
    return terrain, buildings, landuse


# ============================================================================
# SVGP Evaluator
# ============================================================================

class SVGPEvaluator:
    """Evaluator using SVGP model with optional UCB exploration."""
    
    def __init__(
        self,
        model_path: Path,
        parcel_size: int,
        device: torch.device,
        ucb_lambda: float = 0.0
    ):
        self.device = device
        self.ucb_lambda = ucb_lambda
        self.parcel_size = parcel_size
        
        logger.info(f"Loading SVGP model from {model_path}")
        
        # Load checkpoint - contains model AND normalization (62D input + scalar output)
        checkpoint = torch.load(model_path, map_location=device, weights_only=False)
        
        # Extract normalization stats from checkpoint (lowercase keys)
        self.train_X_mean = checkpoint['train_x_mean'].to(device)  # (62,) - genome + width + height
        self.train_X_std = checkpoint['train_x_std'].to(device)    # (62,)
        # Convert scalar tensors to Python floats for correct broadcasting
        self.train_y_mean = checkpoint['train_y_mean'].item() if hasattr(checkpoint['train_y_mean'], 'item') else float(checkpoint['train_y_mean'])
        self.train_y_std = checkpoint['train_y_std'].item() if hasattr(checkpoint['train_y_std'], 'item') else float(checkpoint['train_y_std'])
        
        # Load model using extracted checkpoint
        self.model, self.likelihood = load_svgp_model(str(model_path), device=str(device))
        
        # Initialize fast encoding for feature calculation
        self.fast_encoding = NumbaFastEncoding(parcel_size=parcel_size)
        
        logger.info(f"SVGP loaded (UCB λ={ucb_lambda})")
    
    def _denormalize_genomes(self, genomes: np.ndarray, parcel_size_bins: int) -> np.ndarray:
        """
        Convert normalized 0-1 genomes to pixel-coordinate encoding that SVGP was trained on.
        
        Genome structure: 10 buildings × [width, length, height, x, y, active]
        
        Training encoding:
        - width, length: pixels (range depends on parcel size)
        - height: floors (0-max_floors)
        - x, y: pixel coordinates centered at 0 (range: -parcel_size/2 to +parcel_size/2)
        - active: binary 0/1
        
        Args:
            genomes: (N, 60) normalized genomes in [0, 1]
            parcel_size_bins: Parcel size in bins
        
        Returns:
            (N, 60) denormalized genomes in pixel coordinates
        """
        N = len(genomes)
        genomes_denorm = np.zeros_like(genomes)
        
        max_building_floors = self.fast_encoding.config.get('max_building_floors', 10)
        
        for i in range(10):  # 10 buildings
            base = i * 6
            
            # Width & Length: 0-1 → 0 to parcel_size/2 pixels
            genomes_denorm[:, base + 0] = genomes[:, base + 0] * (parcel_size_bins / 2)
            genomes_denorm[:, base + 1] = genomes[:, base + 1] * (parcel_size_bins / 2)
            
            # Height: 0-1 → 0 to max_floors
            genomes_denorm[:, base + 2] = genomes[:, base + 2] * max_building_floors
            
            # X & Y positions: 0-1 → -parcel_size/2 to +parcel_size/2 (centered at 0)
            genomes_denorm[:, base + 3] = (genomes[:, base + 3] - 0.5) * parcel_size_bins
            genomes_denorm[:, base + 4] = (genomes[:, base + 4] - 0.5) * parcel_size_bins
            
            # Active: 0-1 → 0 or 1 (threshold at 0.5)
            genomes_denorm[:, base + 5] = (genomes[:, base + 5] > 0.5).astype(np.float32)
        
        return genomes_denorm
    
    def evaluate(
        self,
        genomes: np.ndarray,
        parcel_sizes: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Evaluate genomes using SVGP.
        
        Args:
            genomes: (N, 60) genome array in NORMALIZED 0-1 range
            parcel_sizes: (N,) parcel sizes in BINS (not meters!)
        
        Returns:
            Dictionary with:
            - objectives: UCB-adjusted objectives for selection
            - objectives_mean: Pure SVGP mean predictions
            - uncertainties: SVGP standard deviations
            - features: (N, 8) planning features
        """
        N = len(genomes)
        
        # Express genomes to heightmaps
        heightmaps = self.fast_encoding.express_batch(genomes)
        
        # Compute features for archive
        from backend.fast_encoding import numba_calculate_features
        pixel_size = self.fast_encoding.config['xy_scale']
        features = np.zeros((N, 8), dtype=np.float64)
        for i in range(N):
            features[i] = numba_calculate_features(heightmaps[i], pixel_size)
        
        # CRITICAL: Convert normalized 0-1 genomes to pixel-coordinate encoding
        # that SVGP was trained on
        genomes_denorm = self._denormalize_genomes(genomes, parcel_sizes[0])
        
        # Prepare SVGP input: [denormalized_genome (60), width_bins (1), height_bins (1)] = 62D
        widths = parcel_sizes.reshape(-1, 1)
        heights = parcel_sizes.reshape(-1, 1)
        X = np.column_stack([genomes_denorm, widths, heights])
        X_tensor = torch.tensor(X, dtype=torch.float32, device=self.device)
        
        # Normalize
        X_norm = (X_tensor - self.train_X_mean) / self.train_X_std
        
        # Predict with uncertainty
        self.model.eval()
        self.likelihood.eval()
        with torch.no_grad(), gpytorch.settings.fast_pred_var():
            pred = self.likelihood(self.model(X_norm))
            pred_mean = pred.mean * self.train_y_std + self.train_y_mean
            pred_std = pred.stddev * self.train_y_std
        
        objectives_mean = pred_mean.cpu().numpy()
        uncertainties = pred_std.cpu().numpy()
        
        # UCB adjustment
        objectives_adjusted = objectives_mean + self.ucb_lambda * uncertainties
        
        return {
            'objectives': objectives_adjusted,  # For MAP-Elites selection
            'objectives_mean': objectives_mean,  # Pure predictions
            'uncertainties': uncertainties,
            'features': features
        }


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
        
        # ROI mask (region of interest on parcel)
        grid_h, grid_w = 66, 94
        start_row = (grid_h - self.actual_parcel_size_cells) // 2
        start_col = (grid_w - self.actual_parcel_size_cells) // 2
        self.roi_mask = np.zeros((grid_h, grid_w), dtype=bool)
        self.roi_mask[
            start_row:start_row+self.actual_parcel_size_cells,
            start_col:start_col+self.actual_parcel_size_cells
        ] = True
        
        logger.info("U-Net loaded successfully")
    
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
        
        # Construct domain grids
        terrain, buildings, landuse = construct_domain_grids_batch(
            heightmaps,
            self.actual_parcel_size_cells  # Use ACTUAL parcel size, not model size
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
# Hybrid Evaluator (U-Net + SVGP)
# ============================================================================

class HybridEvaluator:
    """
    Hybrid evaluator: U-Net for accuracy + SVGP for uncertainty exploration.
    
    Fitness = U-Net(x) + λ * SVGP_stddev(x)
    """
    
    def __init__(
        self,
        unet_path: Path,
        svgp_path: Path,
        parcel_size: int,
        device: torch.device,
        ucb_lambda: float = 1.0,
        actual_parcel_size: Optional[int] = None
    ):
        self.unet_eval = UNetEvaluator(unet_path, parcel_size, device, actual_parcel_size)
        actual_size = actual_parcel_size if actual_parcel_size else parcel_size
        self.svgp_eval = SVGPEvaluator(svgp_path, actual_size, device, ucb_lambda=0.0)
        self.ucb_lambda = ucb_lambda
        
        logger.info(f"Hybrid evaluator created (λ={ucb_lambda})")
    
    def evaluate(
        self,
        genomes: np.ndarray,
        parcel_sizes: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Evaluate using hybrid approach.
        
        Returns U-Net predictions adjusted by SVGP uncertainty.
        """
        # Get U-Net predictions (most accurate)
        unet_results = self.unet_eval.evaluate(genomes, parcel_sizes)
        
        # Get SVGP uncertainty
        svgp_results = self.svgp_eval.evaluate(genomes, parcel_sizes)
        
        # Combine: U-Net fitness + SVGP exploration bonus
        objectives_adjusted = (
            unet_results['objectives'] + 
            self.ucb_lambda * svgp_results['uncertainties']
        )
        
        return {
            'objectives': objectives_adjusted,  # For MAP-Elites selection
            'objectives_unet': unet_results['objectives'],  # Pure U-Net
            'uncertainties': svgp_results['uncertainties'],  # SVGP stddev
            'features': unet_results['features']
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_evaluator(
    model_type: str,
    parcel_size: int,
    models_dir: Path = Path('models'),
    device: str = 'cuda',
    ucb_lambda: float = 1.0,
    actual_parcel_size: Optional[int] = None
):
    """
    Create appropriate evaluator based on model type.
    
    Args:
        model_type: 'svgp', 'unet', or 'hybrid'
        parcel_size: MODEL parcel size in METERS (e.g., 81 for unet_81m.pth)
        models_dir: Directory containing model files
        device: 'cuda' or 'cpu'
        ucb_lambda: UCB exploration parameter (for SVGP/Hybrid)
        actual_parcel_size: ACTUAL parcel size in meters (may be smaller than model size)
                           If None, assumes actual size == model size
    
    Returns:
        Configured evaluator instance
    
    Raises:
        FileNotFoundError: If model files not found
        ValueError: If model_type invalid
    
    Example:
        # For 17-bin (51m) parcel using 27-bin (81m) U-Net model
        evaluator = create_evaluator('unet', parcel_size=81, actual_parcel_size=51)
    """
    device = torch.device(device if torch.cuda.is_available() else 'cpu')
    
    # Model paths
    # SVGP: Single model for ALL parcel sizes (uses parcel dims as input)
    svgp_path = models_dir / 'svgp.pth'
    # U-Net: Size-specific models (fixed input dimensions)
    unet_path = models_dir / f'unet_{parcel_size}m.pth'
    
    if model_type == 'svgp':
        if not svgp_path.exists():
            raise FileNotFoundError(f"SVGP model not found: {svgp_path}")
        return SVGPEvaluator(svgp_path, parcel_size, device, ucb_lambda)
    
    elif model_type == 'unet':
        if not unet_path.exists():
            raise FileNotFoundError(f"U-Net model not found: {unet_path}")
        return UNetEvaluator(unet_path, parcel_size, device, actual_parcel_size)
    
    elif model_type == 'hybrid':
        if not svgp_path.exists():
            raise FileNotFoundError(f"SVGP model not found: {svgp_path}")
        if not unet_path.exists():
            raise FileNotFoundError(f"U-Net model not found: {unet_path}")
        return HybridEvaluator(unet_path, svgp_path, parcel_size, device, ucb_lambda, actual_parcel_size)
    
    else:
        raise ValueError(f"Invalid model_type: {model_type}. Must be 'svgp', 'unet', or 'hybrid'")
