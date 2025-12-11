# GUI Integration Package - Quick Reference

**Purpose**: Integrate SVGP, U-Net, and Hybrid surrogate models into OpenSKIZZE GUI for 1000× faster optimization.

---

## What's in This Package

| File | Purpose |
|------|---------|
| **INTEGRATION_PROMPT.md** | Complete integration guide with rationale and examples |
| **IMPLEMENTATION_CHECKLIST.md** | Step-by-step checklist (follow this!) |
| **svgp.py** | SVGP model class and loading utilities |
| **unet.py** | U-Net model architecture and config |
| **model_evaluator.py** | Unified evaluator interface (use this!) |
| **fast_encoding.py** | Optimized genome→heightmap encoding (16× faster) |
| **encoding_cfg.yml** | Encoding parameters |
| **domain_cfg.yml** | Feature ranges and labels |
| **README.md** | This file |

---

## Quick Start (5 Minutes)

### 1. Copy Package
```bash
cp -r GUI_INTEGRATION_PACKAGE /path/to/gui_repo/openskizze_optimization/
```

### 2. Copy Models
```bash
# Copy pre-trained models (get from HPC results)
cp results/exp3_hpo/.../svgp_*.pth /path/to/gui_repo/models/
cp results/exp5_unet/.../unet_*.pth /path/to/gui_repo/models/
cp results/.../*_normalization.json /path/to/gui_repo/models/
```

### 3. Install Dependencies
```bash
mamba install torch>=2.0.0 gpytorch>=1.11 numba>=0.57.0
```

### 4. Test
```python
from openskizze_optimization.model_evaluator import create_evaluator

evaluator = create_evaluator('unet', parcel_size=60, device='cuda')
print("✓ Ready to integrate!")
```

---

## Usage Pattern

```python
# Initialize once at optimization start
from openskizze_optimization.model_evaluator import create_evaluator

evaluator = create_evaluator(
    model_type='hybrid',      # 'svgp', 'unet', or 'hybrid'
    parcel_size=60,           # 60, 120, or 240m supported
    models_dir=Path('models'),
    device='cuda',            # or 'cpu'
    ucb_lambda=1.0           # For exploration (SVGP/Hybrid only)
)

# In MAP-Elites loop (called thousands of times)
results = evaluator.evaluate(genomes, parcel_sizes)
objectives = results['objectives']
features = results['features']
uncertainties = results.get('uncertainties', None)  # SVGP/Hybrid only
```

---

## Model Comparison

| Model | R² | Speed | Uncertainty | Best For |
|-------|----|----|-------------|----------|
| **SVGP** | 0.946 | 2ms | ✓ Yes | Fast exploration |
| **U-Net** | 0.997 | 2ms | ✗ No | Highest accuracy |
| **Hybrid** | 0.997 | 3ms | ✓ Yes | Best QD quality |

### Performance vs KLAM_21
- Old (KLAM_21): **~580 hours** for 100K evaluations
- New (SVGP): **~30 min** for 100K evaluations (**1160× faster**)
- New (U-Net): **~53 min** for 100K evaluations (**656× faster**)

---

## Integration Steps (30-60 minutes)

Follow `IMPLEMENTATION_CHECKLIST.md` for detailed steps:

1. ✅ **Setup** (10 min): Copy files, install deps
2. ✅ **Testing** (15 min): Verify models load and evaluate correctly
3. ✅ **Integration** (30 min): Modify GUI code to use evaluators
4. ✅ **Validation** (15 min): Run short optimization, check results

---

## Model Files Required

These must be obtained separately (too large for git):

```
models/
├── svgp_60m.pth                   # SVGP model (~50 MB)
├── svgp_60m_normalization.json    # Input/output stats
├── unet_60m.pth                   # U-Net model (~50 MB)
├── unet_60m_normalization.json    # Input/output stats
├── svgp_120m.pth                  # For 120m parcels
├── unet_120m.pth
├── svgp_240m.pth                  # For 240m parcels
└── unet_240m.pth
```

**Where to get them**:
- SVGP: `results/exp3_hpo/best_models/`
- U-Net: `results/exp5_unet/training_results/`

---

## Available Models by Parcel Size

| Parcel Size | SVGP | U-Net | Status |
|-------------|------|-------|--------|
| 60×60m | ✓ | ✓ | **Available** |
| 120×120m | ✓ | ✓ | **Available** |
| 240×240m | ✓ | ✓ | **Available** |

For unsupported parcel sizes, the GUI should gracefully fallback to KLAM_21 physics.

---

## Key Features

### 1. Unified Interface
One evaluator interface works for all models:
```python
evaluator = create_evaluator(model_type, ...)
results = evaluator.evaluate(genomes, parcel_sizes)
```

### 2. Fast Encoding
16× faster genome→heightmap conversion using Numba JIT:
```python
from fast_encoding import NumbaFastEncoding
encoding = NumbaFastEncoding(parcel_size=60)
heightmaps, features = encoding.express_and_features_batch(genomes, parcel_sizes)
```

### 3. Uncertainty Quantification
SVGP and Hybrid models provide uncertainty estimates for UCB exploration:
```python
uncertainties = results['uncertainties']
fitness_adjusted = results['objectives_mean'] + lambda * uncertainties
```

### 4. GPU Acceleration
Automatic FP16 optimization on NVIDIA GPUs (10× speedup):
```python
evaluator = create_evaluator(..., device='cuda')  # Automatic FP16
```

---

## Troubleshooting

### "Model file not found"
**Solution**: Copy model files from optimization repository.

### "CUDA out of memory"
**Solution**: Use CPU or reduce batch size:
```python
evaluator = create_evaluator(..., device='cpu')
```

### "Slow evaluation"
**Solution**: 
1. Enable GPU: `device='cuda'`
2. Warmup first batch (JIT compilation)
3. Increase batch size

### "Feature mismatch"
**Solution**: Ensure using `fast_encoding.py` with correct `cfg.yml` files.

---

## Testing Before Integration

```bash
# Test model loading
python -c "from openskizze_optimization.model_evaluator import create_evaluator; \
           evaluator = create_evaluator('unet', 60); print('✓ OK')"

# Test evaluation speed
python -c "import numpy as np; from openskizze_optimization.model_evaluator import create_evaluator; \
           evaluator = create_evaluator('unet', 60); genomes = np.random.randn(100, 60); \
           sizes = np.full(100, 60.0); evaluator.evaluate(genomes, sizes); print('✓ OK')"
```

---

## Next Steps

1. **Follow checklist**: `IMPLEMENTATION_CHECKLIST.md`
2. **Read full guide**: `INTEGRATION_PROMPT.md`
3. **Test integration**: Run 100 generations
4. **Validate**: Compare with KLAM_21
5. **Deploy**: Update GUI documentation

---

## Support

- **Repository**: https://github.com/FullDA-FM/openskizze-klam21-optimization
- **Documentation**: `EXPERIMENTS.md`, `TECHNICAL.md`
- **Contact**: info@haggdesign.de

---

## License

AGPLv3 (commercial licensing available)
