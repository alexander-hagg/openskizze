# OpenSKIZZE GUI - Surrogate Model Integration

**Version**: 1.0  
**Date**: December 9, 2025  
**Source Repository**: openskizze-klam21-optimization  
**Target Repository**: OpenSKIZZE GUI

---

## Executive Summary

Integrate three optimized surrogate models (SVGP, U-Net, Hybrid) into the existing OpenSKIZZE GUI to accelerate MAP-Elites optimization from ~580 hours to **~30-60 minutes** while maintaining high accuracy (R² = 0.946-0.997).

**Key Benefits**:
- ⚡ **1000× speedup**: SVGP/U-Net replace expensive KLAM_21 physics simulations
- 🎯 **High accuracy**: U-Net achieves 99.7% variance explained (R² = 0.997)
- 🔍 **Uncertainty quantification**: SVGP provides exploration-exploitation balance
- 🚀 **Optimized code**: Fast encoding (16× speedup) and Numba-JIT features

---

## Integration Overview

### What Needs Integration
🔧 **Model loading**: Load pre-trained SVGP/U-Net models from `models/` directory  
🔧 **Model evaluation**: Replace KLAM_21 calls with surrogate predictions  
🔧 **Fast encoding**: Use optimized `fast_encoding.py` for genome→heightmap  
🔧 **Feature calculation**: Use optimized Numba-JIT feature computation  
🔧 **Model selection UI**: Allow user to choose SVGP/U-Net/Hybrid  

---

## Architecture

```
User selects parcel → User selects model type → MAP-Elites with surrogate (~2-5 ms/eval) → Archive
                      (SVGP/U-Net/Hybrid)       ↑ 1000× FASTER
```

### Model Selection Logic

Currently the UNET model (full flow prediction) is only available for 27x27 parcels (amounting to 81m x 81m), however we will add more models for more parcel sizes later on. The SVGP model was trained on all parcel sizes (and therefore has two more inputs, besides the genome, parcelsize_x and parcelsize_y).

SVGP models were trained on the following parcel sizes:

27x27
33x33
39x39
45x45
51x51
57x57
63x63
69x69
75x75
81x81
99x99
87x87
93x93

---

## File Structure

### This Integration Package Contains

```
GUI_INTEGRATION_PACKAGE/
├── INTEGRATION_PROMPT.md          # This file
├── svgp.py                         # SVGP model class and loading
├── unet.py                         # U-Net model class and config
├── model_evaluator.py              # Unified evaluator interface
├── fast_encoding.py                # Optimized genome encoding
├── encoding_cfg.yml                # Encoding configuration
├── domain_cfg.yml                  # Feature ranges and labels
├── IMPLEMENTATION_CHECKLIST.md     # Step-by-step integration guide
└── README.md                       # Quick reference
```


## Integration Steps

### 1. Install Dependencies

Add to GUI's `environment.yml` and install with mamba:

```bash
mamba install torch>=2.0.0 gpytorch>=1.11 numba>=0.57.0
mamba install numpy>=1.24.0 scipy>=1.10.0 pyyaml>=6.0
```

### 3. Modify Existing MAP-Elites Code

#### A. Add Model Selection to GUI

```python
# In your GUI's optimization setup dialog/panel
model_options = ['SVGP (Fast, uncertainty)', 
                 'U-Net (Most accurate)', 
                 'Hybrid (Accuracy + exploration)']
selected_model = model_dropdown.value  # 'svgp', 'unet', or 'hybrid'
ucb_lambda = ucb_slider.value if selected_model in ['svgp', 'hybrid'] else 0.0
```

#### B. Add the three new Evaluators

```python
from openskizze_optimization.model_evaluator import create_evaluator

# Initialize once at start of optimization
evaluator = create_evaluator(
    model_type=selected_model,  # 'svgp', 'unet', or 'hybrid'
    parcel_size=parcel_size,
    models_dir=Path('models'),
    device='cuda',
    ucb_lambda=1.0  # For SVGP/Hybrid
)

# In MAP-Elites loop (called thousands of times)
results = evaluator.evaluate(genomes, parcel_sizes)
objectives = results['objectives']
features = results['features']
```

#### C. Handle Missing Models Gracefully

```python
from openskizze_optimization.model_evaluator import create_evaluator

def get_available_models(parcel_size: int) -> list:
    """Check which models are available for this parcel size."""
    available = []
    models_dir = Path('models')
    
    if (models_dir / f'svgp_{parcel_size}m.pth').exists():
        available.append('svgp')
    if (models_dir / f'unet_{parcel_size}m.pth').exists():
        available.append('unet')
    if len(available) == 2:
        available.append('hybrid')  # Both SVGP and U-Net available
    
    return available

# In GUI setup
available_models = get_available_models(parcel_size)


### 4. Update Archive Storage

The evaluators return different metadata depending on model type:

```python
# SVGP results
{
    'objectives': array(...),         # UCB-adjusted (if λ > 0)
    'objectives_mean': array(...),    # Pure SVGP predictions
    'uncertainties': array(...),      # Standard deviations
    'features': array(N, 8)           # Planning features
}

# U-Net results
{
    'objectives': array(...),         # Cold air flux predictions
    'features': array(N, 8)           # Planning features
}

# Hybrid results
{
    'objectives': array(...),         # U-Net + λ*SVGP_uncertainty
    'objectives_unet': array(...),    # Pure U-Net predictions
    'uncertainties': array(...),      # SVGP uncertainties
    'features': array(N, 8)           # Planning features
}
```

**Update your archive cell storage**:
```python
# Store both predicted and ground-truth objectives (if validating)
archive.add(
    solution=genome,
    objective=results['objectives'][i],  # For selection/comparison
    measures=results['features'][i],
    metadata={
        'objective_predicted': results['objectives'][i],
        'objective_mean': results.get('objectives_mean', [None])[i],
        'uncertainty': results.get('uncertainties', [None])[i],
        'model_type': selected_model,
        'ucb_lambda': ucb_lambda
    }
)
```

### 5. Performance Optimization Tips

#### Enable GPU (Recommended)
```python
import torch

device = 'cuda' if torch.cuda.is_available() else 'cpu'
evaluator = create_evaluator(..., device=device)
```

#### Batch Evaluation
```python
# Process multiple genomes at once for GPU efficiency
batch_size = 1024  # Good for GPU
genomes_batch = emitter.ask()  # Get batch from emitter
results = evaluator.evaluate(genomes_batch, parcel_sizes_batch)
```

#### Pre-compile Models (Optional)
```python
# For PyTorch 2.0+, compile models at initialization
evaluator = create_evaluator(..., device='cuda')

# First evaluation will be slow (compilation), subsequent fast
warmup_genomes = np.random.randn(32, 60)
warmup_sizes = np.full(32, parcel_size)
_ = evaluator.evaluate(warmup_genomes, warmup_sizes)  # Warmup
```

---

## Testing the Integration

### Minimal Working Example

```python
#!/usr/bin/env python3
"""
Test surrogate model integration.
Run this before integrating into full GUI.
"""

import sys
sys.path.insert(0, 'openskizze_optimization')

import numpy as np
import torch
from pathlib import Path
from model_evaluator import create_evaluator

def test_evaluator(model_type='svgp'):
    """Test evaluator with random genomes."""
    
    print(f"\n{'='*60}")
    print(f"Testing {model_type.upper()} Evaluator")
    print(f"{'='*60}\n")
    
    # Setup
    parcel_size = 27
    n_samples = 100
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    # Create evaluator
    evaluator = create_evaluator(
        model_type=model_type,
        parcel_size=parcel_size,
        models_dir=Path('models'),
        device=device,
        ucb_lambda=1.0
    )
    
    # Generate random genomes (PyRibs convention: N(0,1))
    genomes = np.random.randn(n_samples, 60)
    parcel_sizes = np.full(n_samples, parcel_size, dtype=np.float32)
    
    # Evaluate
    import time
    start = time.time()
    results = evaluator.evaluate(genomes, parcel_sizes)
    elapsed = time.time() - start
    
    # Results
    print(f"✓ Evaluated {n_samples} genomes in {elapsed:.3f}s")
    print(f"  → {elapsed/n_samples*1000:.2f} ms per genome")
    print(f"  → {n_samples/elapsed:.1f} genomes/sec")
    print(f"\nObjectives shape: {results['objectives'].shape}")
    print(f"Objectives range: [{results['objectives'].min():.2f}, {results['objectives'].max():.2f}]")
    print(f"Features shape: {results['features'].shape}")
    
    if 'uncertainties' in results:
        print(f"\n✓ Uncertainty estimates available")
        print(f"  Uncertainty range: [{results['uncertainties'].min():.3f}, {results['uncertainties'].max():.3f}]")
    
    return results

if __name__ == '__main__':
    # Test all model types
    for model_type in ['svgp', 'unet', 'hybrid']:
        try:
            test_evaluator(model_type)
        except FileNotFoundError as e:
            print(f"\n✗ {model_type.upper()} test failed: {e}")
            print(f"  → Make sure models are in models/ directory\n")
```

**Expected Output**:
```
============================================================
Testing SVGP Evaluator
============================================================

✓ Evaluated 100 genomes in 0.124s
  → 1.24 ms per genome
  → 806.5 genomes/sec

Objectives shape: (100,)
Objectives range: [12.45, 87.32]
Features shape: (100, 8)

✓ Uncertainty estimates available
  Uncertainty range: [2.134, 8.567]
```

---

## Validation & Quality Assurance

### 1. Verify Feature Consistency

The fast encoding must produce identical features to the original implementation:

```python
from openskizze_optimization.fast_encoding import NumbaFastEncoding
from encodings.parametric.parametric import ParametricEncoding

# Test genome
genome = np.random.randn(60)
parcel_size = 27

# Old method
old_encoding = ParametricEncoding(size=27, config={...})
old_heightmap = old_encoding.express(genome)
old_features = calculate_planning_features(old_heightmap)

# New method
new_encoding = NumbaFastEncoding(parcel_size=27)
new_heightmap, new_features = new_encoding.express_and_features(genome, parcel_size)

# Verify
assert np.allclose(old_heightmap, new_heightmap, atol=0.01), "Heightmap mismatch!"
assert np.allclose(old_features, new_features, atol=0.01), "Feature mismatch!"
print("✓ Feature consistency verified")
```

### 2. Validate Archive Coverage

After integration, run a short optimization and verify:

```python
# Run 1000 generations with new evaluator
archive = run_mapelites(evaluator, generations=1000)

# Check coverage
coverage = len(archive) / archive.capacity * 100
print(f"Archive coverage: {coverage:.2f}%")

# Expected: 0.5-2% coverage for 1000 gens (similar to old implementation)
assert coverage > 0.1, "Coverage too low - check evaluator integration"
```

### 3. Performance Benchmarks

Compare optimization times:

```python
import time

# Benchmark
start = time.time()
archive = run_mapelites(evaluator, generations=10000)
elapsed = time.time() - start

print(f"10K generations completed in: {elapsed/60:.1f} minutes")

# Expected times:
# SVGP: ~30 min (1024 evals/gen)
# U-Net: ~53 min (1024 evals/gen)
# Hybrid: ~63 min (1024 evals/gen)
# KLAM_21: ~580 hours (1024 evals/gen) ← OLD METHOD
```

---

## Model Performance Summary

| Model | R² | Speed (ms/eval) | Output | Use Case |
|-------|----|--------------------|--------|----------|
| **SVGP** | 0.946 | ~2ms | Scalar + uncertainty | Fast, exploration |
| **U-Net** | 0.997 | ~2ms | Scalar (+ spatial fields) | Highest accuracy |
| **Hybrid** | 0.997 | ~3ms | U-Net + SVGP uncertainty | Best QD quality |

### When to Use Each Model

- **SVGP**: Fast prototyping, uncertainty-aware optimization, UCB exploration
- **U-Net**: Production optimization, highest accuracy, validated results
- **Hybrid**: Research, maximum QD score, combines best of both

### Model Limitations

⚠️ **Current**: UNET: Only 27×27m parcel size supported but will be expanded later on  
⚠️ **Training data**: Models trained on SAIL archives (high-fitness region)  
⚠️ **Generalization**: Best performance on similar building typologies  
⚠️ **Validation**: Validate top N solutions with real KLAM_21 if critical  

---

## Troubleshooting

### "Feature mismatch in archive"
```
AssertionError: Feature values outside expected ranges
```
**Solution**: Ensure you're using `fast_encoding.py` with correct `cfg.yml` files.

### "CUDA out of memory"
```
RuntimeError: CUDA out of memory
```
**Solution**: Reduce batch size or use CPU device:
```python
evaluator = create_evaluator(..., device='cpu')
```

### "Slow evaluation speed"
```
Taking 50ms per genome instead of 2ms
```
**Solution**: 
1. Enable GPU: `device='cuda'`
2. Use FP16: Automatic on GPU
3. Warmup first batch: JIT compilation overhead

### "Archive coverage too low"
```
Only 0.01% coverage after 1000 generations
```
**Solution**: Check evaluator is returning correct objectives and features ranges match `domain_cfg.yml`.

---

## Future Extensions

### Adding More Parcel Sizes

When models for additional parcel sizes become available:

1. Train models for target size (33m, 39m, etc.)
2. Save as `models/svgp_{size}m.pth` and `models/unet_{size}m.pth`
3. Include `normalization.json` files
4. Update `get_available_models()` - it will automatically detect new models
5. Test with validation script

### Multi-Scale U-Net (Coming Soon)

```python
# Single model handles all parcel sizes
evaluator = create_evaluator(
    model_type='unet_multiscale',
    parcel_size=51,  # Or any size 27-99m
    models_dir=Path('models')
)
```

---

## Quick Reference

### Import Pattern
```python
from openskizze_optimization.model_evaluator import create_evaluator
evaluator = create_evaluator('hybrid', parcel_size=27, device='cuda', ucb_lambda=1.0)
```

### Evaluation Pattern
```python
results = evaluator.evaluate(genomes, parcel_sizes)
objectives = results['objectives']
features = results['features']
```


### Dependencies
```
torch>=2.0.0, gpytorch>=1.11, numba>=0.57.0
```

---
