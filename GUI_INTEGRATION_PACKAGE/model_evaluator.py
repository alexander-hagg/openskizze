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
1. SVGP model (fast, provides uncertainty)
2. U-Net model (most accurate, no uncertainty)
3. Hybrid model (U-Net fitness + SVGP uncertainty for exploration)

All evaluators use the optimized fast_encoding.py for consistent feature
calculation and performance.

Usage:
    from model_evaluator import create_evaluator
    
    # Create evaluator
    evaluator = create_evaluator(
        model_type='hybrid',  # or 'svgp' or 'unet'
        parcel_size=60,
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

from svgp import SVGPModel, load_svgp_model
from unet import UNet, UNetConfig
from fast_encoding import NumbaFastEncoding

logger = logging.getLogger(__name__)


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
        self.model, self.likelihood = load_svgp_model(str(model_path), device=str(device))
        
        # Load normalization stats
        norm_path = model_path.parent / 'normalization.json'
        with open(norm_path) as f:
            norm_stats = json.load(f)
        
        self.train_X_mean = torch.tensor(norm_stats['train_X_mean'], device=device)
        self.train_X_std = torch.tensor(norm_stats['train_X_std'], device=device)
        self.train_y_mean = norm_stats['train_y_mean']
        self.train_y_std = norm_stats['train_y_std']
        
        # Initialize fast encoding for feature calculation
        self.fast_encoding = NumbaFastEncoding(parcel_size=parcel_size)
        
        logger.info(f"SVGP loaded (UCB λ={ucb_lambda})")
    
    def evaluate(
        self,
        genomes: np.ndarray,
        parcel_sizes: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Evaluate genomes using SVGP.
        
        Args:
            genomes: (N, 60) genome array
            parcel_sizes: (N,) parcel sizes in meters
        
        Returns:
            Dictionary with:
            - objectives: UCB-adjusted objectives for selection
            - objectives_mean: Pure SVGP mean predictions
            - uncertainties: SVGP standard deviations
            - features: (N, 8) planning features
        """
        N = len(genomes)
        
        # Compute features (needed for archive)
        heightmaps, features = self.fast_encoding.express_and_features_batch(
            genomes,
            parcel_sizes
        )
        
        # Prepare SVGP input: [genome (60), width (1), height (1)] = 62D
        widths = parcel_sizes.reshape(-1, 1)
        heights = parcel_sizes.reshape(-1, 1)
        X = np.column_stack([genomes, widths, heights])
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
        device: torch.device
    ):
        self.device = device
        self.parcel_size = parcel_size
        self.parcel_size_cells = parcel_size // 3  # 3m per cell
        
        logger.info(f"Loading U-Net model from {model_path}")
        
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
        
        # Load normalization stats
        norm_path = model_path.parent / 'normalization.json'
        with open(norm_path) as f:
            norm_stats = json.load(f)
        
        self.terrain_mean = norm_stats['input']['terrain']['mean']
        self.terrain_std = norm_stats['input']['terrain']['std']
        self.buildings_mean = norm_stats['input']['buildings']['mean']
        self.buildings_std = norm_stats['input']['buildings']['std']
        self.landuse_mean = norm_stats['input']['landuse']['mean']
        self.landuse_std = norm_stats['input']['landuse']['std']
        self.output_means = {k: v['mean'] for k, v in norm_stats['output'].items()}
        self.output_stds = {k: v['std'] for k, v in norm_stats['output'].items()}
        
        # Initialize fast encoding
        self.fast_encoding = NumbaFastEncoding(parcel_size=parcel_size)
        
        # Calculate grid dimensions (must match training data)
        xy_scale = 3.0
        environment_xy_size = 200
        env_size_m = max(environment_xy_size, parcel_size * 3)
        env_cells_base = int(env_size_m / xy_scale)
        original_offset = (env_cells_base - self.parcel_size_cells) // 2
        left_extension = original_offset
        
        self.grid_h = env_cells_base
        self.grid_w = env_cells_base + left_extension
        
        # ROI mask (region of interest on parcel)
        offset_x = original_offset + left_extension
        offset_y = original_offset
        self.roi_mask = np.zeros((self.grid_h, self.grid_w), dtype=bool)
        self.roi_mask[
            offset_y:offset_y+self.parcel_size_cells,
            offset_x:offset_x+self.parcel_size_cells
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
        # Compute heightmaps and features
        heightmaps, features = self.fast_encoding.express_and_features_batch(
            genomes,
            parcel_sizes
        )
        
        # Construct domain grids with dynamic sizing
        terrain, buildings, landuse = construct_domain_grids_batch(
            heightmaps,
            self.parcel_size
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
        
        # Denormalize outputs
        Y_pred = Y_pred.float().cpu().numpy()
        Ex = Y_pred[:, 0, :, :] * self.output_stds['Ex'] + self.output_means['Ex']
        uq = Y_pred[:, 2, :, :] * self.output_stds['uq'] + self.output_means['uq']
        vq = Y_pred[:, 3, :, :] * self.output_stds['vq'] + self.output_means['vq']
        
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
        ucb_lambda: float = 1.0
    ):
        self.unet_eval = UNetEvaluator(unet_path, parcel_size, device)
        self.svgp_eval = SVGPEvaluator(svgp_path, parcel_size, device, ucb_lambda=0.0)
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
    ucb_lambda: float = 1.0
):
    """
    Create appropriate evaluator based on model type.
    
    Args:
        model_type: 'svgp', 'unet', or 'hybrid'
        parcel_size: Parcel size in meters (e.g., 60)
        models_dir: Directory containing model files
        device: 'cuda' or 'cpu'
        ucb_lambda: UCB exploration parameter (for SVGP/Hybrid)
    
    Returns:
        Configured evaluator instance
    
    Raises:
        FileNotFoundError: If model files not found
        ValueError: If model_type invalid
    
    Example:
        evaluator = create_evaluator('hybrid', parcel_size=60, ucb_lambda=1.0)
        results = evaluator.evaluate(genomes, parcel_sizes)
    """
    device = torch.device(device if torch.cuda.is_available() else 'cpu')
    
    # Model paths
    svgp_path = models_dir / f'svgp_{parcel_size}m.pth'
    unet_path = models_dir / f'unet_{parcel_size}m.pth'
    
    if model_type == 'svgp':
        if not svgp_path.exists():
            raise FileNotFoundError(f"SVGP model not found: {svgp_path}")
        return SVGPEvaluator(svgp_path, parcel_size, device, ucb_lambda)
    
    elif model_type == 'unet':
        if not unet_path.exists():
            raise FileNotFoundError(f"U-Net model not found: {unet_path}")
        return UNetEvaluator(unet_path, parcel_size, device)
    
    elif model_type == 'hybrid':
        if not svgp_path.exists():
            raise FileNotFoundError(f"SVGP model not found: {svgp_path}")
        if not unet_path.exists():
            raise FileNotFoundError(f"U-Net model not found: {unet_path}")
        return HybridEvaluator(unet_path, svgp_path, parcel_size, device, ucb_lambda)
    
    else:
        raise ValueError(f"Invalid model_type: {model_type}. Must be 'svgp', 'unet', or 'hybrid'")
