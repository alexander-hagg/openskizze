#!/usr/bin/env python3
"""
Surrogate Evaluator Wrapper for OpenSKIZZE

Bridges the existing eval_batch() interface with the new surrogate model evaluators.
Maintains compatibility with the optimizer's expected output format.
"""

import numpy as np
import torch
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple, Any

from backend.model_evaluator import create_evaluator, SVGPEvaluator, UNetEvaluator, HybridEvaluator
from backend.fast_encoding import NumbaFastEncoding
from backend.config import SURROGATE_CONFIG, DOMAIN_CONFIG

logger = logging.getLogger(__name__)


def get_parcel_size_bins_from_session(session_data: Dict[str, Any]) -> Optional[int]:
    """
    Extract parcel size in bins from session data.
    
    Args:
        session_data: Session dictionary containing grid_params
    
    Returns:
        Parcel size in bins (e.g., 27 for 81m at 3m/bin), or None if not available
    """
    if not session_data:
        return None
    
    grid_params = session_data.get('grid_params')
    if not grid_params:
        return None
    
    # grid_params should contain xy_length (size in bins)
    parcel_size_bins = grid_params.get('xy_length')
    return parcel_size_bins


def get_available_models(parcel_size_bins: Optional[int]) -> Dict[str, bool]:
    """
    Check which surrogate models are available for the given parcel size.
    
    SVGP: Single model works for ALL parcel sizes (uses parcel dimensions as input)
    U-Net: Requires size-specific model (fixed input dimensions)
    Hybrid: Requires both SVGP and U-Net
    
    Args:
        parcel_size_bins: Parcel size in bins (e.g., 27 for 81m at 3m/bin)
    
    Returns:
        Dictionary with model availability: {'svgp': bool, 'unet': bool, 'hybrid': bool}
    """
    print("\n[SURROGATE DEBUG] get_available_models called")
    print(f"  - parcel_size_bins: {parcel_size_bins}")
    
    models_dir = Path(SURROGATE_CONFIG['models_dir'])
    print(f"  - models_dir: {models_dir}")
    print(f"  - models_dir exists: {models_dir.exists()}")
    
    # Check SVGP model (single model works for ALL parcel sizes)
    # Normalization stored IN checkpoint, not separate file
    svgp_path = models_dir / SURROGATE_CONFIG['svgp_model_name']
    svgp_available = svgp_path.exists()
    print(f"  - SVGP model: {svgp_path}")
    print(f"  - SVGP model exists: {svgp_path.exists()}")
    print(f"  - SVGP available: {svgp_available} (works for ALL parcel sizes, normalization in checkpoint)")
    
    # For U-Net, we need to know the parcel size
    unet_available = False
    hybrid_available = False
    
    if parcel_size_bins is None:
        print("  - parcel_size_bins is None, U-Net/Hybrid cannot be determined")
        print(f"  - Returning: {{'svgp': {svgp_available}, 'unet': False, 'hybrid': False}}")
        return {'svgp': svgp_available, 'unet': False, 'hybrid': False}
    
    parcel_size_m = parcel_size_bins * DOMAIN_CONFIG['pixel_size_in_meters']
    print(f"  - parcel_size_bins: {parcel_size_bins}, parcel_size_m: {int(parcel_size_m)}m")
    
    # Check U-Net model: Find smallest model >= required parcel size
    # U-Net can handle smaller parcels via ROI masking (centered in training domain)
    # available_parcel_sizes_unet is in BINS, need to convert to meters for comparison
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    available_unet_sizes_bins = sorted(SURROGATE_CONFIG['available_parcel_sizes_unet'])
    suitable_unet_sizes_bins = [s for s in available_unet_sizes_bins if s * pixel_size >= parcel_size_m]
    
    unet_available = False
    selected_unet_size = None
    if suitable_unet_sizes_bins:
        # Try each suitable size from smallest to largest
        for unet_size_bins in suitable_unet_sizes_bins:
            unet_size_m = unet_size_bins * pixel_size
            unet_path = models_dir / f"unet_{int(unet_size_m)}m.pth"
            unet_norm_path = models_dir / f"unet_{int(unet_size_m)}m_normalization.json"
            if unet_path.exists() and unet_norm_path.exists():
                unet_available = True
                selected_unet_size = unet_size_m
                print(f"  - U-Net model: Using {int(unet_size_m)}m model ({unet_size_bins} bins) for {int(parcel_size_m)}m parcel ({parcel_size_bins} bins)")
                print(f"  - U-Net model path: {unet_path}")
                print(f"  - U-Net normalization path: {unet_norm_path}")
                break
    
    if not unet_available:
        available_sizes_m = [s * pixel_size for s in available_unet_sizes_bins]
        print(f"  - WARNING: No suitable U-Net model for {int(parcel_size_m)}m parcel ({parcel_size_bins} bins)")
        print(f"  - Need model >= {int(parcel_size_m)}m. Available sizes: {[int(s) for s in available_sizes_m]}m")
    
    print(f"  - U-Net available: {unet_available}")
    
    # Hybrid requires both
    hybrid_available = svgp_available and unet_available
    print(f"  - Hybrid available: {hybrid_available} (needs both SVGP + U-Net)")
    
    # List all .pth files in models directory if it exists
    if models_dir.exists():
        pth_files = list(models_dir.glob('*.pth'))
        print(f"  - Found .pth files in {models_dir}: {[f.name for f in pth_files]}")
    else:
        print(f"  - Models directory does not exist!")
    
    result = {
        'svgp': svgp_available,
        'unet': unet_available,
        'hybrid': hybrid_available,
        'selected_unet_size': selected_unet_size  # Size in meters of the selected U-Net model
    }
    print(f"  - Returning: {result}")
    
    return result


class SurrogateEvaluatorWrapper:
    """
    Wrapper that provides eval_batch-compatible interface for surrogate models.
    
    Handles:
    - Model initialization and caching
    - Batch evaluation with GPU acceleration
    - Output format conversion to match eval_batch() expectations
    - Performance logging (background only)
    - Flow field storage for U-Net visualization
    """
    
    def __init__(
        self,
        model_type: str,
        parcel_size_bins: int,
        ucb_lambda: float = 1.0,
        device: str = 'auto'
    ):
        """
        Initialize surrogate evaluator.
        
        Args:
            model_type: 'svgp', 'unet', or 'hybrid'
            parcel_size_bins: Parcel size in bins (e.g., 27 for 81m at 3m/bin)
            ucb_lambda: UCB exploration parameter (for SVGP/Hybrid)
            device: 'cuda', 'cpu', or 'auto'
        """
        self.model_type = model_type
        self.parcel_size_bins = parcel_size_bins
        self.parcel_size_meters = parcel_size_bins * DOMAIN_CONFIG['pixel_size_in_meters']
        self.ucb_lambda = ucb_lambda
        
        # Device selection
        if device == 'auto':
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        # Performance tracking
        self.total_evaluations = 0
        self.total_time_seconds = 0.0
        
        # Flow field storage (for U-Net visualization)
        self.last_flow_fields = None
        self.last_uncertainties = None
        
        # Initialize evaluator
        models_dir = Path(SURROGATE_CONFIG['models_dir'])
        
        # Determine actual model size to use (for U-Net, may be larger than parcel)
        if model_type in ['unet', 'hybrid']:
            # Find smallest suitable U-Net model
            # available_parcel_sizes_unet is in BINS, need to convert to meters
            pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
            available_unet_sizes_bins = sorted(SURROGATE_CONFIG['available_parcel_sizes_unet'])
            suitable_sizes_bins = [s for s in available_unet_sizes_bins if s * pixel_size >= self.parcel_size_meters]
            actual_model_size = None
            
            for size_bins in suitable_sizes_bins:
                size_m = size_bins * pixel_size
                unet_path = models_dir / f"unet_{int(size_m)}m.pth"
                unet_norm_path = models_dir / f"unet_{int(size_m)}m_normalization.json"
                if unet_path.exists() and unet_norm_path.exists():
                    actual_model_size = size_m
                    logger.info(f"  Using U-Net model: {int(size_m)}m ({size_bins} bins) for {self.parcel_size_meters}m parcel ({parcel_size_bins} bins)")
                    break
            
            if actual_model_size is None:
                available_sizes_m = [int(s * pixel_size) for s in available_unet_sizes_bins]
                raise ValueError(f"No suitable U-Net model found for {self.parcel_size_meters}m parcel. Available: {available_sizes_m}m")
            
            # Use the actual model size for U-Net initialization
            model_parcel_size = actual_model_size
        else:
            # SVGP works with any parcel size
            model_parcel_size = self.parcel_size_meters
        
        self.evaluator = create_evaluator(
            model_type=model_type,
            parcel_size=model_parcel_size,  # Model size (e.g., 81m)
            models_dir=models_dir,
            device=self.device,
            ucb_lambda=ucb_lambda,
            actual_parcel_size=self.parcel_size_meters  # Actual parcel size (e.g., 51m)
        )
        
        # Fast encoding for heightmap generation
        self.fast_encoding = NumbaFastEncoding(parcel_size=self.parcel_size_meters)
        
        logger.info(f"SurrogateEvaluatorWrapper initialized:")
        logger.info(f"  Model: {model_type}")
        logger.info(f"  Parcel: {parcel_size_bins} bins ({self.parcel_size_meters}m)")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  UCB λ: {ucb_lambda}")
    
    def evaluate_batch(
        self,
        genomes: np.ndarray,
        encoding_obj,
        env_config: dict
    ) -> np.ndarray:
        """
        Evaluate batch of genomes using surrogate model.
        
        Returns same format as eval_batch():
        np.array of shape (N, 1 + num_features + heightmap_size)
        where each row is [fitness, feature1, feature2, ..., heightmap_flat]
        
        Args:
            genomes: (N, 60) genome array
            encoding_obj: ParametricEncoding instance (for compatibility, uses fast_encoding internally)
            env_config: Environment configuration dict
        
        Returns:
            results: (N, 1 + num_features + grid_size^2) array
        """
        N = len(genomes)
        start_time = time.time()
        
        # Create parcel sizes array (all same size)
        parcel_sizes = np.full(N, self.parcel_size_meters, dtype=np.float32)
        
        # Evaluate using surrogate model
        results = self.evaluator.evaluate(genomes, parcel_sizes)
        
        # Extract results
        objectives = results['objectives']  # (N,)
        features = results['features']  # (N, 8)
        
        # Store uncertainties if available (for heatmap visualization)
        if 'uncertainties' in results:
            self.last_uncertainties = results['uncertainties']
        else:
            self.last_uncertainties = None
        
        # Store flow fields if available (for U-Net visualization)
        if 'flow_fields' in results:
            self.last_flow_fields = results['flow_fields']
        else:
            self.last_flow_fields = None
        
        # Generate heightmaps for archive storage
        heightmaps = self.fast_encoding.express_batch(genomes)  # (N, D, D)
        grid_size = heightmaps.shape[1]
        heightmaps_flat = heightmaps.reshape(N, -1)  # (N, D*D)
        
        # Get selected features based on env_config
        selected_indices = env_config.get('selected_features', list(range(8)))
        selected_features = features[:, selected_indices]  # (N, num_selected)
    
        
        # Combine into expected output format: [fitness, features..., heightmap_flat]
        output = np.column_stack([
            objectives.reshape(-1, 1),
            selected_features,
            heightmaps_flat
        ])
        
        # Performance logging (background only)
        elapsed = time.time() - start_time
        self.total_evaluations += N
        self.total_time_seconds += elapsed
        
        avg_ms = (elapsed / N) * 1000
        logger.debug(f"Surrogate batch: {N} genomes in {elapsed:.3f}s ({avg_ms:.2f}ms/genome)")
        
        return output
    
    def get_performance_stats(self) -> Dict[str, float]:
        """Get cumulative performance statistics."""
        if self.total_evaluations == 0:
            return {'total_evaluations': 0, 'total_time_s': 0, 'avg_ms_per_eval': 0}
        
        return {
            'total_evaluations': self.total_evaluations,
            'total_time_s': self.total_time_seconds,
            'avg_ms_per_eval': (self.total_time_seconds / self.total_evaluations) * 1000,
            'evals_per_second': self.total_evaluations / self.total_time_seconds
        }
    
    def get_last_uncertainties(self) -> Optional[np.ndarray]:
        """Get uncertainties from last evaluation batch (for heatmap)."""
        return self.last_uncertainties
    
    def get_last_flow_fields(self) -> Optional[np.ndarray]:
        """Get flow fields from last U-Net evaluation (for visualization)."""
        return self.last_flow_fields


def create_surrogate_wrapper(
    model_type: str,
    parcel_size_bins: int,
    ucb_lambda: float = 1.0
) -> Optional[SurrogateEvaluatorWrapper]:
    """
    Factory function to create surrogate evaluator wrapper.
    
    Args:
        model_type: 'svgp', 'unet', or 'hybrid'
        parcel_size_bins: Parcel size in bins
        ucb_lambda: UCB exploration parameter
    
    Returns:
        SurrogateEvaluatorWrapper instance, or None if model not available
    """
    available = get_available_models(parcel_size_bins)
    
    if not available.get(model_type, False):
        logger.error(f"Model '{model_type}' not available for parcel size {parcel_size_bins} bins")
        return None
    
    try:
        return SurrogateEvaluatorWrapper(
            model_type=model_type,
            parcel_size_bins=parcel_size_bins,
            ucb_lambda=ucb_lambda,
            device='auto'  # Use GPU when available
        )
    except Exception as e:
        logger.error(f"Failed to create surrogate evaluator: {e}")
        return None
