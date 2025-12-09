# OpenSKIZZE Surrogate Model Integration Plan

**Version**: 1.0  
**Date**: December 9, 2025  
**Branch**: `modelintegration`  
**Author**: AI Assistant  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [File Operations Checklist](#3-file-operations-checklist)
4. [Detailed Implementation Steps](#4-detailed-implementation-steps)
5. [Code Specifications](#5-code-specifications)
6. [UI Specifications](#6-ui-specifications)
7. [Translation Strings](#7-translation-strings)
8. [Testing Requirements](#8-testing-requirements)
9. [Implementation Order](#9-implementation-order)

---

## 1. Executive Summary

### Goal
Integrate three pre-trained surrogate models (SVGP, U-Net, Hybrid) into OpenSKIZZE's MAP-Elites optimization workflow.

### Key Benefits
- **1000× speedup**: ~2-5ms per evaluation vs. ~10 seconds for physics simulation
- **Uncertainty quantification**: SVGP/Hybrid provide exploration-exploitation balance
- **High accuracy**: U-Net achieves R² = 0.997

### Design Decisions (Per User Request)
| Decision | Choice |
|----------|--------|
| Model file location | `models/` directory |
| Default behavior | Surrogate requires **explicit selection** (default = original physics) |
| Flow visualization | **Include now** (U-Net flow field visualization) |
| Uncertainty display | **Add as extra heatmap** in archive visualization |
| Performance logging | **Background only** (console/file), not in GUI |

### Parcel Size Support
- **SVGP**: All sizes (27, 33, 39, 45, 51, 57, 63, 69, 75, 81, 87, 93, 99 bins)
- **U-Net**: Currently only 27 bins (81m × 81m parcels)
- **Hybrid**: Requires both SVGP and U-Net (currently only 27 bins)

---

## 2. Architecture Overview

### Current Architecture
```
step2_constraints.py          step3_optimize.py              backend/optimizer.py
     ↓                               ↓                              ↓
[Feature Selection]  →  [Start Optimization]  →  run_qd_optimization()
[Hard Constraints]                                       ↓
[QD Hyperparams]                                  eval_batch() (multiprocess)
                                                         ↓
                                              compute_fitness_street_canyon()
```

### Target Architecture
```
step2_constraints.py          step3_optimize.py              backend/optimizer.py
     ↓                               ↓                              ↓
[Feature Selection]  →  [Start Optimization]  →  run_qd_optimization()
[Hard Constraints]                                       ↓
[QD Hyperparams]                                    ┌────┴────┐
[MODEL SELECTOR]                                    ↓         ↓
[UCB Lambda]                                   SURROGATE   ORIGINAL
     ↓                                         (GPU batch) (multiproc)
[Model Info Cards]                                  ↓
                                           model_evaluator.py
                                           ┌───────┼───────┐
                                           ↓       ↓       ↓
                                         SVGP   U-Net   Hybrid
                                           ↓       ↓
                                     uncertainties  flow_field
                                           ↓       ↓
                                    uncertainty   flow
                                     heatmap    visualization
```

---

## 3. File Operations Checklist

### 3.1 New Files to Create

| File Path | Description |
|-----------|-------------|
| `backend/surrogate_evaluator.py` | Wrapper integrating model_evaluator with existing interface |
| `models/.gitkeep` | Placeholder for model directory |

### 3.2 Files to Copy from Integration Package

| Source | Destination |
|--------|-------------|
| `GUI_INTEGRATION_PACKAGE/model_evaluator.py` | `backend/model_evaluator.py` |
| `GUI_INTEGRATION_PACKAGE/svgp.py` | `backend/svgp.py` |
| `GUI_INTEGRATION_PACKAGE/unet.py` | `backend/unet.py` |
| `GUI_INTEGRATION_PACKAGE/fast_encoding.py` | `backend/fast_encoding.py` |
| `GUI_INTEGRATION_PACKAGE/domain_cfg.yml` | `backend/domain_cfg.yml` |
| `GUI_INTEGRATION_PACKAGE/encoding_cfg.yml` | `backend/encoding_cfg.yml` |

### 3.3 Files to Modify

| File | Changes Required |
|------|------------------|
| `requirements.txt` | Add torch, gpytorch |
| `backend/config.py` | Add SURROGATE_CONFIG |
| `backend/translation.py` | Add model selector strings (DE/EN) |
| `backend/optimizer.py` | Add surrogate evaluator branch |
| `backend/optimization_process.py` | Accept model config, create evaluator |
| `pages/step2_constraints.py` | Add model selector UI with info cards |
| `pages/step3_optimize.py` | Pass model settings, log performance |
| `pages/step4_analysis.py` | Add uncertainty heatmap option |
| `pages/step6_compare_detail.py` | Add flow field visualization |

---

## 4. Detailed Implementation Steps

### Step 4.1: Update requirements.txt

**Location**: `/requirements.txt`

**Add these lines**:
```
torch>=2.0.0
gpytorch>=1.11
```

---

### Step 4.2: Copy Integration Package Files

**Commands**:
```bash
cp GUI_INTEGRATION_PACKAGE/model_evaluator.py backend/
cp GUI_INTEGRATION_PACKAGE/svgp.py backend/
cp GUI_INTEGRATION_PACKAGE/unet.py backend/
cp GUI_INTEGRATION_PACKAGE/fast_encoding.py backend/
cp GUI_INTEGRATION_PACKAGE/domain_cfg.yml backend/
cp GUI_INTEGRATION_PACKAGE/encoding_cfg.yml backend/
mkdir -p models
touch models/.gitkeep
```

---

### Step 4.3: Create backend/surrogate_evaluator.py

**Purpose**: Bridge between existing `eval_batch()` interface and new surrogate models.

**Full file content**:
```python
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
        self.evaluator = create_evaluator(
            model_type=model_type,
            parcel_size=self.parcel_size_meters,
            models_dir=models_dir,
            device=self.device,
            ucb_lambda=ucb_lambda
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


def get_available_models(parcel_size_bins: int) -> Dict[str, bool]:
    """
    Check which models are available for a given parcel size.
    
    Args:
        parcel_size_bins: Parcel size in bins (3m per bin)
    
    Returns:
        Dict with model availability: {'original': True, 'svgp': bool, 'unet': bool, 'hybrid': bool}
    """
    models_dir = Path(SURROGATE_CONFIG['models_dir'])
    parcel_size_m = parcel_size_bins * DOMAIN_CONFIG['pixel_size_in_meters']
    
    available = {
        'original': True,  # Always available
        'svgp': False,
        'unet': False,
        'hybrid': False
    }
    
    # Check SVGP
    svgp_path = models_dir / f'svgp_{parcel_size_m}m.pth'
    if svgp_path.exists():
        available['svgp'] = True
    
    # Check U-Net
    unet_path = models_dir / f'unet_{parcel_size_m}m.pth'
    if unet_path.exists():
        available['unet'] = True
    
    # Hybrid requires both
    if available['svgp'] and available['unet']:
        available['hybrid'] = True
    
    return available


def get_parcel_size_bins_from_session(session_data: dict) -> Optional[int]:
    """
    Calculate parcel size in bins from session data.
    
    Args:
        session_data: Session store data containing site_polygon
    
    Returns:
        Parcel size in bins (3m per bin), or None if cannot determine
    """
    if not session_data or 'site_polygon' not in session_data:
        return None
    
    try:
        import geopandas as gpd
        import math
        
        user_polygon_geojson = session_data['site_polygon']
        gdf_user_poly = gpd.GeoDataFrame.from_features(user_polygon_geojson, crs="EPSG:4326")
        gdf_user_poly_native = gdf_user_poly.to_crs("EPSG:25832")
        min_x, min_y, max_x, max_y = gdf_user_poly_native.total_bounds
        
        width = max_x - min_x
        height = max_y - min_y
        square_size = max(width, height)
        
        pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
        parcel_size_bins = int(math.ceil(square_size / pixel_size))
        
        return parcel_size_bins
    except Exception as e:
        logger.warning(f"Could not determine parcel size: {e}")
        return None


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
            ucb_lambda=ucb_lambda
        )
    except Exception as e:
        logger.error(f"Failed to create surrogate evaluator: {e}")
        return None
```

---

### Step 4.4: Modify backend/config.py

**Location**: After `DOMAIN_CONFIG` definition (around line 50)

**Add this block**:
```python
SURROGATE_CONFIG = {
    'models_dir': 'models',
    'available_parcel_sizes_svgp': [27, 33, 39, 45, 51, 57, 63, 69, 75, 81, 87, 93, 99],
    'available_parcel_sizes_unet': [27],  # Currently only 27 bins, expand later
    'default_ucb_lambda': 1.0,
    'default_model_type': 'original',  # Explicit selection required
}
```

---

### Step 4.5: Modify backend/optimizer.py

**Current code** (lines 10-12):
```python
from backend.evaluation import eval_batch

def run_qd_optimization(encoding_obj, env_config: dict, qd_config: dict, x0_adaptive=None, progress_callback=None):
```

**Replace with**:
```python
from backend.evaluation import eval_batch
import logging

logger = logging.getLogger(__name__)

def run_qd_optimization(encoding_obj, env_config: dict, qd_config: dict, x0_adaptive=None, progress_callback=None):
```

**Current code** (lines 43-48):
```python
    for gen in range(1, qd_config['num_generations'] + 1):
        try:
            genomes = scheduler.ask()
            results = eval_batch(genomes, encoding_obj, env_config, pool)            
            objectives = results[:, 0]
            features = results[:, 1:len(env_config['labels']) + 1]
```

**Replace with**:
```python
    # Check if using surrogate model
    use_surrogate = env_config.get('use_surrogate', False)
    surrogate_wrapper = env_config.get('surrogate_wrapper', None)
    
    if use_surrogate and surrogate_wrapper is not None:
        logger.info(f"Using SURROGATE evaluation: {surrogate_wrapper.model_type}")
    else:
        logger.info("Using ORIGINAL physics-based evaluation")
    
    for gen in range(1, qd_config['num_generations'] + 1):
        try:
            genomes = scheduler.ask()
            
            # Branch: Surrogate (GPU batch) vs Original (multiprocess)
            if use_surrogate and surrogate_wrapper is not None:
                results = surrogate_wrapper.evaluate_batch(genomes, encoding_obj, env_config)
            else:
                results = eval_batch(genomes, encoding_obj, env_config, pool)
            
            objectives = results[:, 0]
            features = results[:, 1:len(env_config['labels']) + 1]
```

**After optimization loop ends** (after `pool.join()`, around line 75), add:
```python
    # Log surrogate performance stats if used
    if use_surrogate and surrogate_wrapper is not None:
        stats = surrogate_wrapper.get_performance_stats()
        logger.info(f"Surrogate Performance Summary:")
        logger.info(f"  Total evaluations: {stats['total_evaluations']}")
        logger.info(f"  Total time: {stats['total_time_s']:.2f}s")
        logger.info(f"  Avg per evaluation: {stats['avg_ms_per_eval']:.2f}ms")
        logger.info(f"  Throughput: {stats['evals_per_second']:.1f} evals/sec")
```

---

### Step 4.6: Modify backend/optimization_process.py

**Current function signature** (line 19):
```python
def create_environment(user_polygon_geojson: dict, selected_features: list, user_feature_ranges: dict, hard_constraints: dict = None, cached_building_data: dict = None, feature_set: str = 'consolidated'):
```

**Replace with**:
```python
def create_environment(user_polygon_geojson: dict, selected_features: list, user_feature_ranges: dict, hard_constraints: dict = None, cached_building_data: dict = None, feature_set: str = 'consolidated', model_type: str = 'original', ucb_lambda: float = 1.0):
```

**At the end of create_environment()**, before the return statement, add:
```python
    # === SURROGATE MODEL SETUP ===
    use_surrogate = model_type != 'original'
    surrogate_wrapper = None
    
    if use_surrogate:
        from backend.surrogate_evaluator import create_surrogate_wrapper, get_parcel_size_bins_from_session
        
        # Calculate parcel size in bins
        parcel_size_bins = res  # res is already calculated above
        
        surrogate_wrapper = create_surrogate_wrapper(
            model_type=model_type,
            parcel_size_bins=parcel_size_bins,
            ucb_lambda=ucb_lambda
        )
        
        if surrogate_wrapper is None:
            print(f"[create_environment] WARNING: Could not create surrogate wrapper for {model_type}")
            print("[create_environment] Falling back to original evaluation")
            use_surrogate = False
```

**Modify the env_config dict** to include surrogate fields:
```python
    env_config = {
        # ... existing fields ...
        'use_surrogate': use_surrogate,
        'model_type': model_type,
        'ucb_lambda': ucb_lambda,
        'surrogate_wrapper': surrogate_wrapper,
    }
```

---

### Step 4.7: Modify pages/step2_constraints.py - Add Model Selector UI

**Location**: After the QD Hyperparameters section (around line 135), still inside the advanced mode div

**Add this new section** (after `html.Div(id='qd-hyperparams-container', ...)`):
```python
                # --- NEW: Surrogate Model Selection Section (shown only in advanced mode) ---
                html.Div(id='surrogate-model-container', children=[
                    html.H5(T[lang]['STEP2_SURROGATE_MODEL_HEADER'], className="mt-4"),
                    
                    # Model Type Selection with Info Cards
                    dbc.Card(dbc.CardBody([
                        dbc.Label(T[lang]['STEP2_MODEL_TYPE_LABEL'], className="fw-bold"),
                        
                        dbc.RadioItems(
                            id='model-type-radio',
                            options=[
                                {'label': T[lang]['STEP2_MODEL_ORIGINAL'], 'value': 'original'},
                                {'label': T[lang]['STEP2_MODEL_SVGP'], 'value': 'svgp'},
                                {'label': T[lang]['STEP2_MODEL_UNET'], 'value': 'unet'},
                                {'label': T[lang]['STEP2_MODEL_HYBRID'], 'value': 'hybrid'},
                            ],
                            value='original',
                            className="mb-3"
                        ),
                        
                        # Model Info Card (dynamic based on selection)
                        html.Div(id='model-info-card'),
                        
                        # UCB Lambda Slider (shown for SVGP/Hybrid only)
                        html.Div(id='ucb-lambda-container', children=[
                            dbc.Label(T[lang]['STEP2_UCB_LAMBDA_LABEL'], className="mt-3"),
                            dcc.Slider(
                                id='ucb-lambda-slider',
                                min=0.0, max=3.0, step=0.1, value=1.0,
                                marks={0: '0 (Pure accuracy)', 1: '1 (Balanced)', 2: '2', 3: '3 (Max exploration)'},
                                tooltip={"placement": "bottom", "always_visible": False}
                            ),
                            html.Small(T[lang]['STEP2_UCB_LAMBDA_INFO'], className="text-muted"),
                        ], style={'display': 'none'}),
                        
                        # Model availability warning
                        html.Div(id='model-availability-warning', className="mt-2"),
                        
                    ]), color="light"),
                ], style={'display': 'none'}),  # Hidden by default (advanced mode)
```

**Add these callbacks** at the end of the file:

```python
@callback(
    Output('surrogate-model-container', 'style'),
    Input('advanced-mode-toggle', 'value')
)
def toggle_surrogate_container(advanced_mode):
    """Show/hide surrogate model selection based on advanced mode."""
    if advanced_mode and 1 in advanced_mode:
        return {'display': 'block'}
    return {'display': 'none'}


@callback(
    Output('model-info-card', 'children'),
    Input('model-type-radio', 'value'),
    State('language-store', 'data')
)
def update_model_info_card(model_type, lang):
    """Display info card explaining the selected model."""
    if lang is None:
        lang = 'DE'
    
    info_cards = {
        'original': dbc.Alert([
            html.H6(T[lang]['MODEL_INFO_ORIGINAL_TITLE'], className="alert-heading"),
            html.P(T[lang]['MODEL_INFO_ORIGINAL_DESC']),
            html.Hr(),
            html.Small([
                html.Strong(T[lang]['MODEL_INFO_SPEED']), " ~10s/evaluation",
                html.Br(),
                html.Strong(T[lang]['MODEL_INFO_ACCURACY']), " Ground truth (physics)",
                html.Br(),
                html.Strong(T[lang]['MODEL_INFO_UNCERTAINTY']), " Not available"
            ])
        ], color="secondary"),
        
        'svgp': dbc.Alert([
            html.H6(T[lang]['MODEL_INFO_SVGP_TITLE'], className="alert-heading"),
            html.P(T[lang]['MODEL_INFO_SVGP_DESC']),
            html.Hr(),
            html.Small([
                html.Strong(T[lang]['MODEL_INFO_SPEED']), " ~2ms/evaluation (5000× faster)",
                html.Br(),
                html.Strong(T[lang]['MODEL_INFO_ACCURACY']), " R² = 0.946",
                html.Br(),
                html.Strong(T[lang]['MODEL_INFO_UNCERTAINTY']), " ✓ Available (enables exploration)"
            ])
        ], color="info"),
        
        'unet': dbc.Alert([
            html.H6(T[lang]['MODEL_INFO_UNET_TITLE'], className="alert-heading"),
            html.P(T[lang]['MODEL_INFO_UNET_DESC']),
            html.Hr(),
            html.Small([
                html.Strong(T[lang]['MODEL_INFO_SPEED']), " ~2ms/evaluation (5000× faster)",
                html.Br(),
                html.Strong(T[lang]['MODEL_INFO_ACCURACY']), " R² = 0.997 (highest)",
                html.Br(),
                html.Strong(T[lang]['MODEL_INFO_UNCERTAINTY']), " Not available",
                html.Br(),
                html.Strong(T[lang]['MODEL_INFO_FLOW']), " ✓ Flow field visualization"
            ])
        ], color="success"),
        
        'hybrid': dbc.Alert([
            html.H6(T[lang]['MODEL_INFO_HYBRID_TITLE'], className="alert-heading"),
            html.P(T[lang]['MODEL_INFO_HYBRID_DESC']),
            html.Hr(),
            html.Small([
                html.Strong(T[lang]['MODEL_INFO_SPEED']), " ~3ms/evaluation (3000× faster)",
                html.Br(),
                html.Strong(T[lang]['MODEL_INFO_ACCURACY']), " R² = 0.997 (U-Net accuracy)",
                html.Br(),
                html.Strong(T[lang]['MODEL_INFO_UNCERTAINTY']), " ✓ Available (SVGP uncertainty)",
                html.Br(),
                html.Strong(T[lang]['MODEL_INFO_FLOW']), " ✓ Flow field visualization"
            ])
        ], color="primary"),
    }
    
    return info_cards.get(model_type, info_cards['original'])


@callback(
    Output('ucb-lambda-container', 'style'),
    Input('model-type-radio', 'value')
)
def toggle_ucb_slider(model_type):
    """Show UCB lambda slider only for models with uncertainty."""
    if model_type in ['svgp', 'hybrid']:
        return {'display': 'block'}
    return {'display': 'none'}


@callback(
    Output('model-type-radio', 'options'),
    Output('model-availability-warning', 'children'),
    Input('session-store', 'data'),
    State('language-store', 'data')
)
def update_model_availability(session_data, lang):
    """Enable/disable models based on parcel size and model availability."""
    if lang is None:
        lang = 'DE'
    
    from backend.surrogate_evaluator import get_available_models, get_parcel_size_bins_from_session
    
    # Default options (all disabled except original)
    default_options = [
        {'label': T[lang]['STEP2_MODEL_ORIGINAL'], 'value': 'original'},
        {'label': T[lang]['STEP2_MODEL_SVGP'] + f" ({T[lang]['MODEL_UNAVAILABLE']})", 'value': 'svgp', 'disabled': True},
        {'label': T[lang]['STEP2_MODEL_UNET'] + f" ({T[lang]['MODEL_UNAVAILABLE']})", 'value': 'unet', 'disabled': True},
        {'label': T[lang]['STEP2_MODEL_HYBRID'] + f" ({T[lang]['MODEL_UNAVAILABLE']})", 'value': 'hybrid', 'disabled': True},
    ]
    
    if not session_data or 'site_polygon' not in session_data:
        return default_options, dbc.Alert(T[lang]['MODEL_SELECT_PARCEL_FIRST'], color="warning", className="mt-2")
    
    parcel_size_bins = get_parcel_size_bins_from_session(session_data)
    if parcel_size_bins is None:
        return default_options, dbc.Alert(T[lang]['MODEL_CANNOT_DETERMINE_SIZE'], color="warning", className="mt-2")
    
    available = get_available_models(parcel_size_bins)
    
    options = [
        {'label': T[lang]['STEP2_MODEL_ORIGINAL'], 'value': 'original'},
    ]
    
    # SVGP
    if available['svgp']:
        options.append({'label': T[lang]['STEP2_MODEL_SVGP'], 'value': 'svgp'})
    else:
        options.append({'label': T[lang]['STEP2_MODEL_SVGP'] + f" ({T[lang]['MODEL_UNAVAILABLE']})", 'value': 'svgp', 'disabled': True})
    
    # U-Net
    if available['unet']:
        options.append({'label': T[lang]['STEP2_MODEL_UNET'], 'value': 'unet'})
    else:
        options.append({'label': T[lang]['STEP2_MODEL_UNET'] + f" ({T[lang]['MODEL_UNAVAILABLE']})", 'value': 'unet', 'disabled': True})
    
    # Hybrid
    if available['hybrid']:
        options.append({'label': T[lang]['STEP2_MODEL_HYBRID'], 'value': 'hybrid'})
    else:
        options.append({'label': T[lang]['STEP2_MODEL_HYBRID'] + f" ({T[lang]['MODEL_UNAVAILABLE']})", 'value': 'hybrid', 'disabled': True})
    
    # Warning message
    warning = None
    parcel_size_m = parcel_size_bins * 3
    if not available['svgp'] and not available['unet']:
        warning = dbc.Alert(
            T[lang]['MODEL_NONE_AVAILABLE'].format(size=parcel_size_m),
            color="warning", className="mt-2"
        )
    elif not available['unet']:
        warning = dbc.Alert(
            T[lang]['MODEL_UNET_UNAVAILABLE'].format(size=parcel_size_m),
            color="info", className="mt-2"
        )
    
    return options, warning
```

**Modify the session store callback** to save model settings:

Find the callback that saves to session-store and add:
```python
# In the callback that updates session-store
session_data['model_type'] = model_type_value  # from model-type-radio
session_data['ucb_lambda'] = ucb_lambda_value  # from ucb-lambda-slider
```

---

### Step 4.8: Modify pages/step3_optimize.py

**Find the optimization callback** (the one that calls `start_optimization` or `create_environment`)

**Add model settings extraction** from session:
```python
# Get model settings from session (default to original)
model_type = session_data.get('model_type', 'original')
ucb_lambda = session_data.get('ucb_lambda', 1.0)

# Log selection
import logging
logger = logging.getLogger(__name__)
logger.info(f"Optimization starting with model_type={model_type}, ucb_lambda={ucb_lambda}")
```

**Pass to create_environment**:
```python
env_config, encoding_obj, phenotype_info = create_environment(
    user_polygon_geojson=session_data['site_polygon'],
    selected_features=selected_features,
    user_feature_ranges=user_feature_ranges,
    hard_constraints=hard_constraints,
    cached_building_data=cached_building_data,
    feature_set='consolidated',
    model_type=model_type,      # NEW
    ucb_lambda=ucb_lambda       # NEW
)
```

---

### Step 4.9: Modify pages/step4_analysis.py - Add Uncertainty Heatmap

**Find the archive heatmap visualization section**

**Add uncertainty toggle** (if SVGP/Hybrid was used):
```python
# Add after existing heatmap controls
html.Div(id='uncertainty-heatmap-container', children=[
    dbc.Label(T[lang]['STEP4_SHOW_UNCERTAINTY']),
    dbc.Switch(
        id='show-uncertainty-switch',
        value=False,
        label=T[lang]['STEP4_UNCERTAINTY_OVERLAY']
    ),
    dcc.Graph(id='uncertainty-heatmap-graph', style={'display': 'none'})
], style={'display': 'none'})  # Hidden if no uncertainty data
```

**Add callback** to show/hide uncertainty heatmap:
```python
@callback(
    Output('uncertainty-heatmap-container', 'style'),
    Output('uncertainty-heatmap-graph', 'figure'),
    Output('uncertainty-heatmap-graph', 'style'),
    Input('results-store', 'data'),
    Input('show-uncertainty-switch', 'value'),
    State('language-store', 'data')
)
def update_uncertainty_heatmap(results_data, show_uncertainty, lang):
    """Display uncertainty heatmap if available."""
    if lang is None:
        lang = 'DE'
    
    # Check if uncertainty data exists
    if not results_data or 'uncertainty_data' not in results_data:
        return {'display': 'none'}, {}, {'display': 'none'}
    
    # Show container
    container_style = {'display': 'block', 'marginTop': '20px'}
    
    if not show_uncertainty:
        return container_style, {}, {'display': 'none'}
    
    # Create uncertainty heatmap
    uncertainty_data = results_data['uncertainty_data']
    
    import plotly.express as px
    fig = px.imshow(
        uncertainty_data,
        labels={'color': T[lang]['UNCERTAINTY_LABEL']},
        title=T[lang]['STEP4_UNCERTAINTY_HEATMAP_TITLE'],
        color_continuous_scale='Reds'
    )
    fig.update_layout(
        xaxis_title=T[lang]['FEATURE_X'],
        yaxis_title=T[lang]['FEATURE_Y']
    )
    
    return container_style, fig, {'display': 'block'}
```

---

### Step 4.10: Modify pages/step6_compare_detail.py - Add Flow Field Visualization

**Find the 3D comparison visualization section**

**Add flow field toggle** (if U-Net/Hybrid was used):
```python
# Add in the visualization controls
html.Div(id='flow-field-container', children=[
    dbc.Label(T[lang]['STEP6_SHOW_FLOW']),
    dbc.Switch(
        id='show-flow-switch',
        value=False,
        label=T[lang]['STEP6_FLOW_OVERLAY']
    ),
    dcc.Graph(id='flow-field-graph', style={'display': 'none'})
], style={'display': 'none'})  # Hidden if no flow data
```

**Add callback** for flow field visualization:
```python
@callback(
    Output('flow-field-container', 'style'),
    Output('flow-field-graph', 'figure'),
    Output('flow-field-graph', 'style'),
    Input('comparison-store', 'data'),
    Input('show-flow-switch', 'value'),
    State('language-store', 'data')
)
def update_flow_visualization(comparison_data, show_flow, lang):
    """Display flow field visualization if available."""
    if lang is None:
        lang = 'DE'
    
    # Check if flow data exists
    if not comparison_data or 'flow_field' not in comparison_data:
        return {'display': 'none'}, {}, {'display': 'none'}
    
    container_style = {'display': 'block', 'marginTop': '20px'}
    
    if not show_flow:
        return container_style, {}, {'display': 'none'}
    
    # Create flow field visualization (quiver plot)
    flow_data = comparison_data['flow_field']
    uq = flow_data['uq']  # u-component
    vq = flow_data['vq']  # v-component
    
    import plotly.figure_factory as ff
    import numpy as np
    
    # Create grid
    x = np.arange(uq.shape[1])
    y = np.arange(uq.shape[0])
    
    # Subsample for visibility
    step = max(1, uq.shape[0] // 20)
    x_sub = x[::step]
    y_sub = y[::step]
    uq_sub = uq[::step, ::step]
    vq_sub = vq[::step, ::step]
    
    fig = ff.create_quiver(
        x_sub, y_sub, uq_sub, vq_sub,
        scale=0.5,
        arrow_scale=0.3,
        name=T[lang]['FLOW_VECTORS'],
        line=dict(color='blue', width=1)
    )
    
    fig.update_layout(
        title=T[lang]['STEP6_FLOW_TITLE'],
        xaxis_title=T[lang]['POSITION_X'],
        yaxis_title=T[lang]['POSITION_Y'],
        showlegend=True
    )
    
    return container_style, fig, {'display': 'block'}
```

---

## 5. Code Specifications

### 5.1 Model Evaluator Output Format

The surrogate evaluator must return data in this format to maintain compatibility:

```python
# eval_batch() output shape: (N, 1 + num_selected_features + grid_size^2)
# Example for 8 features, 27×27 grid:
# output[i] = [fitness, f0, f1, f2, f3, f4, f5, f6, f7, h0, h1, ..., h728]
```

### 5.2 Flow Field Data Structure

```python
# Flow field structure stored in results/comparison store
flow_field = {
    'Ex': np.ndarray,  # Cold air excess (66×94)
    'uq': np.ndarray,  # u-component velocity (66×94)
    'vq': np.ndarray,  # v-component velocity (66×94)
    'roi_mask': np.ndarray,  # Region of interest mask
}
```

### 5.3 Uncertainty Data Structure

```python
# Uncertainty stored per archive cell
uncertainty_data = {
    'grid': np.ndarray,  # (n_niches, n_niches) uncertainty values
    'min': float,
    'max': float,
    'mean': float
}
```

---

## 6. UI Specifications

### 6.1 Model Selector Appearance

```
┌─────────────────────────────────────────────────────────────┐
│ ⚙️ Surrogate Model (Fast Optimization)                      │
├─────────────────────────────────────────────────────────────┤
│ Evaluation Method:                                          │
│                                                             │
│ ○ Original (Physics-based)                                  │
│ ○ SVGP (Fast + Uncertainty)                                 │
│ ○ U-Net (Highest Accuracy)                                  │
│ ○ Hybrid (Both)                                             │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🔵 SVGP - Sparse Variational Gaussian Process           │ │
│ │                                                         │ │
│ │ Uses a probabilistic model trained on optimization      │ │
│ │ archives. Provides uncertainty estimates that guide     │ │
│ │ exploration of unexplored design regions.               │ │
│ │                                                         │ │
│ │ ───────────────────────────────────────────────────     │ │
│ │ Speed: ~2ms/evaluation (5000× faster)                   │ │
│ │ Accuracy: R² = 0.946                                    │ │
│ │ Uncertainty: ✓ Available (enables exploration)          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Exploration Parameter (λ):                                  │
│ ├───────────────●───────────────────────────────────┤      │
│ 0 (Pure accuracy)    1 (Balanced)              3 (Max)     │
│                                                             │
│ Higher values encourage exploring uncertain regions         │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Uncertainty Heatmap Appearance

- Overlay toggle in Step 4 analysis view
- Color scale: Reds (low uncertainty = light, high = dark)
- Positioned next to or overlaid on fitness heatmap

### 6.3 Flow Field Visualization Appearance

- Toggle switch in Step 6 comparison view
- Quiver (arrow) plot showing wind vectors
- Blue arrows on transparent/semi-transparent building footprint

---

## 7. Translation Strings

### Add to backend/translation.py

```python
# ============================================================================
# SURROGATE MODEL TRANSLATIONS
# ============================================================================

# German (DE)
T['DE']['STEP2_SURROGATE_MODEL_HEADER'] = "Surrogate-Modell (Schnelle Optimierung)"
T['DE']['STEP2_MODEL_TYPE_LABEL'] = "Evaluierungsmethode:"
T['DE']['STEP2_MODEL_ORIGINAL'] = "Original (Physik-basiert)"
T['DE']['STEP2_MODEL_SVGP'] = "SVGP (Schnell + Unsicherheit)"
T['DE']['STEP2_MODEL_UNET'] = "U-Net (Höchste Genauigkeit)"
T['DE']['STEP2_MODEL_HYBRID'] = "Hybrid (Beides)"
T['DE']['STEP2_UCB_LAMBDA_LABEL'] = "Explorationsparameter (λ):"
T['DE']['STEP2_UCB_LAMBDA_INFO'] = "Höhere Werte fördern die Erkundung unsicherer Regionen"

# Model Info Cards
T['DE']['MODEL_INFO_ORIGINAL_TITLE'] = "Original - Physik-basierte Simulation"
T['DE']['MODEL_INFO_ORIGINAL_DESC'] = "Verwendet die vollständige KLAM_21 Kaltluftströmungssimulation. Höchste Genauigkeit, aber langsam."
T['DE']['MODEL_INFO_SVGP_TITLE'] = "SVGP - Sparse Variational Gaussian Process"
T['DE']['MODEL_INFO_SVGP_DESC'] = "Probabilistisches Modell trainiert auf Optimierungsarchiven. Liefert Unsicherheitsschätzungen für gezielte Exploration."
T['DE']['MODEL_INFO_UNET_TITLE'] = "U-Net - Neuronales Netz"
T['DE']['MODEL_INFO_UNET_DESC'] = "Tiefes neuronales Netz für räumliche Vorhersagen. Höchste Genauigkeit unter den Surrogat-Modellen."
T['DE']['MODEL_INFO_HYBRID_TITLE'] = "Hybrid - Kombination aus U-Net und SVGP"
T['DE']['MODEL_INFO_HYBRID_DESC'] = "Nutzt U-Net für Genauigkeit und SVGP für Unsicherheitsschätzungen. Beste Qualitätsdiversitäts-Ergebnisse."

T['DE']['MODEL_INFO_SPEED'] = "Geschwindigkeit:"
T['DE']['MODEL_INFO_ACCURACY'] = "Genauigkeit:"
T['DE']['MODEL_INFO_UNCERTAINTY'] = "Unsicherheit:"
T['DE']['MODEL_INFO_FLOW'] = "Strömungsfeld:"

T['DE']['MODEL_UNAVAILABLE'] = "Nicht verfügbar"
T['DE']['MODEL_SELECT_PARCEL_FIRST'] = "Bitte wählen Sie zuerst eine Parzelle in Schritt 1."
T['DE']['MODEL_CANNOT_DETERMINE_SIZE'] = "Parzellengröße konnte nicht ermittelt werden."
T['DE']['MODEL_NONE_AVAILABLE'] = "Keine Surrogate-Modelle für Parzellengröße {size}m verfügbar."
T['DE']['MODEL_UNET_UNAVAILABLE'] = "U-Net/Hybrid nicht verfügbar für Parzellengröße {size}m. SVGP kann verwendet werden."

# Step 4 - Uncertainty Heatmap
T['DE']['STEP4_SHOW_UNCERTAINTY'] = "Unsicherheit anzeigen"
T['DE']['STEP4_UNCERTAINTY_OVERLAY'] = "Unsicherheits-Overlay"
T['DE']['STEP4_UNCERTAINTY_HEATMAP_TITLE'] = "Modell-Unsicherheit"
T['DE']['UNCERTAINTY_LABEL'] = "Unsicherheit (σ)"

# Step 6 - Flow Field
T['DE']['STEP6_SHOW_FLOW'] = "Strömungsfeld anzeigen"
T['DE']['STEP6_FLOW_OVERLAY'] = "Windströmungs-Overlay"
T['DE']['STEP6_FLOW_TITLE'] = "Kaltluftströmung (U-Net Vorhersage)"
T['DE']['FLOW_VECTORS'] = "Strömungsvektoren"
T['DE']['POSITION_X'] = "Position X (m)"
T['DE']['POSITION_Y'] = "Position Y (m)"
T['DE']['FEATURE_X'] = "Merkmal X"
T['DE']['FEATURE_Y'] = "Merkmal Y"

# English (EN)
T['EN']['STEP2_SURROGATE_MODEL_HEADER'] = "Surrogate Model (Fast Optimization)"
T['EN']['STEP2_MODEL_TYPE_LABEL'] = "Evaluation Method:"
T['EN']['STEP2_MODEL_ORIGINAL'] = "Original (Physics-based)"
T['EN']['STEP2_MODEL_SVGP'] = "SVGP (Fast + Uncertainty)"
T['EN']['STEP2_MODEL_UNET'] = "U-Net (Highest Accuracy)"
T['EN']['STEP2_MODEL_HYBRID'] = "Hybrid (Both)"
T['EN']['STEP2_UCB_LAMBDA_LABEL'] = "Exploration Parameter (λ):"
T['EN']['STEP2_UCB_LAMBDA_INFO'] = "Higher values encourage exploring uncertain regions"

# Model Info Cards
T['EN']['MODEL_INFO_ORIGINAL_TITLE'] = "Original - Physics-based Simulation"
T['EN']['MODEL_INFO_ORIGINAL_DESC'] = "Uses the full KLAM_21 cold air flow simulation. Highest accuracy but slow."
T['EN']['MODEL_INFO_SVGP_TITLE'] = "SVGP - Sparse Variational Gaussian Process"
T['EN']['MODEL_INFO_SVGP_DESC'] = "Probabilistic model trained on optimization archives. Provides uncertainty estimates for targeted exploration."
T['EN']['MODEL_INFO_UNET_TITLE'] = "U-Net - Neural Network"
T['EN']['MODEL_INFO_UNET_DESC'] = "Deep neural network for spatial predictions. Highest accuracy among surrogate models."
T['EN']['MODEL_INFO_HYBRID_TITLE'] = "Hybrid - Combination of U-Net and SVGP"
T['EN']['MODEL_INFO_HYBRID_DESC'] = "Uses U-Net for accuracy and SVGP for uncertainty estimates. Best quality-diversity results."

T['EN']['MODEL_INFO_SPEED'] = "Speed:"
T['EN']['MODEL_INFO_ACCURACY'] = "Accuracy:"
T['EN']['MODEL_INFO_UNCERTAINTY'] = "Uncertainty:"
T['EN']['MODEL_INFO_FLOW'] = "Flow field:"

T['EN']['MODEL_UNAVAILABLE'] = "Not available"
T['EN']['MODEL_SELECT_PARCEL_FIRST'] = "Please select a parcel in Step 1 first."
T['EN']['MODEL_CANNOT_DETERMINE_SIZE'] = "Could not determine parcel size."
T['EN']['MODEL_NONE_AVAILABLE'] = "No surrogate models available for parcel size {size}m."
T['EN']['MODEL_UNET_UNAVAILABLE'] = "U-Net/Hybrid not available for parcel size {size}m. SVGP can be used."

# Step 4 - Uncertainty Heatmap
T['EN']['STEP4_SHOW_UNCERTAINTY'] = "Show Uncertainty"
T['EN']['STEP4_UNCERTAINTY_OVERLAY'] = "Uncertainty Overlay"
T['EN']['STEP4_UNCERTAINTY_HEATMAP_TITLE'] = "Model Uncertainty"
T['EN']['UNCERTAINTY_LABEL'] = "Uncertainty (σ)"

# Step 6 - Flow Field
T['EN']['STEP6_SHOW_FLOW'] = "Show Flow Field"
T['EN']['STEP6_FLOW_OVERLAY'] = "Wind Flow Overlay"
T['EN']['STEP6_FLOW_TITLE'] = "Cold Air Flow (U-Net Prediction)"
T['EN']['FLOW_VECTORS'] = "Flow Vectors"
T['EN']['POSITION_X'] = "Position X (m)"
T['EN']['POSITION_Y'] = "Position Y (m)"
T['EN']['FEATURE_X'] = "Feature X"
T['EN']['FEATURE_Y'] = "Feature Y"
```

---

## 8. Testing Requirements

### 8.1 Unit Tests

Create `tests/test_surrogate_integration.py`:

```python
"""
Tests for surrogate model integration.
"""

import numpy as np
import pytest
from pathlib import Path

def test_surrogate_config_exists():
    """Test that SURROGATE_CONFIG is defined."""
    from backend.config import SURROGATE_CONFIG
    assert 'models_dir' in SURROGATE_CONFIG
    assert 'default_model_type' in SURROGATE_CONFIG

def test_get_available_models_no_models():
    """Test model availability when no models present."""
    from backend.surrogate_evaluator import get_available_models
    # Assuming models directory is empty for this test
    available = get_available_models(27)
    assert available['original'] == True

def test_surrogate_wrapper_creation():
    """Test surrogate wrapper can be created (if models exist)."""
    from backend.surrogate_evaluator import create_surrogate_wrapper, get_available_models
    
    available = get_available_models(27)
    if available['svgp']:
        wrapper = create_surrogate_wrapper('svgp', 27, ucb_lambda=1.0)
        assert wrapper is not None
        assert wrapper.model_type == 'svgp'

def test_parcel_size_detection():
    """Test parcel size detection from session data."""
    from backend.surrogate_evaluator import get_parcel_size_bins_from_session
    
    # Empty session should return None
    assert get_parcel_size_bins_from_session({}) is None
    assert get_parcel_size_bins_from_session(None) is None

def test_output_format_compatibility():
    """Test that surrogate output matches eval_batch format."""
    from backend.surrogate_evaluator import create_surrogate_wrapper, get_available_models
    
    available = get_available_models(27)
    if not available['svgp']:
        pytest.skip("SVGP model not available")
    
    wrapper = create_surrogate_wrapper('svgp', 27)
    
    # Create mock data
    genomes = np.random.randn(10, 60)
    env_config = {'selected_features': [0, 1, 2, 3, 4, 5, 6, 7]}
    
    # Evaluate
    results = wrapper.evaluate_batch(genomes, None, env_config)
    
    # Check shape: (N, 1 + 8 features + 27*27 heightmap)
    expected_cols = 1 + 8 + 27*27
    assert results.shape == (10, expected_cols)
```

### 8.2 Integration Tests

Create `tests/test_surrogate_optimization.py`:

```python
"""
Integration tests for surrogate optimization.
"""

def test_full_optimization_with_svgp():
    """Run short optimization with SVGP model."""
    # Only run if models available
    pass

def test_full_optimization_with_unet():
    """Run short optimization with U-Net model."""
    pass

def test_fallback_to_original():
    """Test that missing models fall back to original."""
    pass
```

---

## 9. Implementation Order

### Phase 1: Backend Foundation (Estimated: 2-3 hours)

1. ☐ Update `requirements.txt` with torch, gpytorch
2. ☐ Copy integration package files to `backend/`
3. ☐ Create `backend/surrogate_evaluator.py` (full file provided above)
4. ☐ Add `SURROGATE_CONFIG` to `backend/config.py`
5. ☐ Create `models/` directory with `.gitkeep`

### Phase 2: Optimizer Integration (Estimated: 1-2 hours)

6. ☐ Modify `backend/optimizer.py` - add surrogate branch
7. ☐ Modify `backend/optimization_process.py` - accept model config

### Phase 3: UI Integration (Estimated: 2-3 hours)

8. ☐ Add all translation strings to `backend/translation.py`
9. ☐ Modify `pages/step2_constraints.py` - add model selector UI
10. ☐ Modify `pages/step3_optimize.py` - pass model settings

### Phase 4: Visualization Features (Estimated: 2-3 hours)

11. ☐ Modify `pages/step4_analysis.py` - add uncertainty heatmap
12. ☐ Modify `pages/step6_compare_detail.py` - add flow field visualization

### Phase 5: Testing & Polish (Estimated: 1-2 hours)

13. ☐ Create test files
14. ☐ Test with actual model files
15. ☐ Handle edge cases

---

## Appendix A: Model File Requirements

### Required Model Files

Place these in `models/` directory:

```
models/
├── svgp_81m.pth                    # SVGP for 27-bin (81m) parcels
├── svgp_81m_normalization.json     # Normalization stats
├── unet_81m.pth                    # U-Net for 27-bin parcels
├── unet_81m_normalization.json     # Normalization stats
└── .gitkeep                        # Placeholder
```

**Note**: File naming uses meters (81m = 27 bins × 3m/bin)

### Obtaining Model Files

See `GUI_INTEGRATION_PACKAGE/MODEL_FILES_LOCATION.md` for instructions on copying trained models from the optimization repository.

---

## Appendix B: Performance Expectations

| Model | Batch Size | Time/Batch | Time/Genome | Speedup vs Original |
|-------|------------|------------|-------------|---------------------|
| Original | 64 | ~640s | ~10s | 1× (baseline) |
| SVGP | 1024 | ~2s | ~2ms | ~5000× |
| U-Net | 1024 | ~2s | ~2ms | ~5000× |
| Hybrid | 1024 | ~3s | ~3ms | ~3300× |

---

## Appendix C: Logging Configuration

Performance is logged to console/file only (not GUI). Example log output:

```
[INFO] SurrogateEvaluatorWrapper initialized:
[INFO]   Model: svgp
[INFO]   Parcel: 27 bins (81m)
[INFO]   Device: cuda
[INFO]   UCB λ: 1.0
[INFO] Using SURROGATE evaluation: svgp
[DEBUG] Surrogate batch: 1024 genomes in 1.842s (1.80ms/genome)
...
[INFO] Surrogate Performance Summary:
[INFO]   Total evaluations: 102400
[INFO]   Total time: 183.42s
[INFO]   Avg per evaluation: 1.79ms
[INFO]   Throughput: 558.3 evals/sec
```

---

*End of Integration Plan*
