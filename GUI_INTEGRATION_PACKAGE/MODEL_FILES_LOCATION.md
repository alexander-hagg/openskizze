# Model Files Location Guide

This document explains where to find the pre-trained model files needed for GUI integration.

---

## Required Files

You need 4 files total:

```
models/
├── svgp_60m.pth                   (~50 MB)
├── svgp_60m_normalization.json    (~2 KB)
├── unet_60m.pth                   (~50 MB)
└── unet_60m_normalization.json    (~5 KB)
```

---

## SVGP Model Files

### Location in Optimization Repository

**Model checkpoint**:
```
results/exp3_hpo/hyperparameterization/
  └── dataset_optimized_numind2000_kmeansinit/
      └── best_model.pth
```

**Normalization stats**:
```
results/exp3_hpo/hyperparameterization/
  └── dataset_optimized_numind2000_kmeansinit/
      └── normalization.json
```

### Where These Come From

These are created by the hyperparameter optimization experiment (Experiment 3):
- Script: `experiments/exp3_hpo/train_gp_hpo.py`
- Config: 2000 inducing points, K-means initialization
- Training data: Optimized SAIL archives (Experiment 1)

### Copy Commands

```bash
# From optimization repo root
cp results/exp3_hpo/hyperparameterization/dataset_optimized_numind2000_kmeansinit/best_model.pth \
   /path/to/gui_repo/models/svgp_60m.pth

cp results/exp3_hpo/hyperparameterization/dataset_optimized_numind2000_kmeansinit/normalization.json \
   /path/to/gui_repo/models/svgp_60m_normalization.json
```

---

## U-Net Model Files

### Location in Optimization Repository

**Model checkpoint**:
```
results/exp5_unet/training_results/
  └── best_model.pth
```

**Normalization stats**:
```
results/exp5_unet/training_results/
  └── normalization.json
```

### Where These Come From

These are created by the U-Net training experiment (Experiment 5):
- Script: `experiments/exp5_unet/train_unet_klam.py`
- Architecture: Small U-Net (64 base channels, depth=4)
- Training data: Spatial KLAM_21 fields from SAIL archives

### Copy Commands

```bash
# From optimization repo root
cp results/exp5_unet/training_results/best_model.pth \
   /path/to/gui_repo/models/unet_60m.pth

cp results/exp5_unet/training_results/normalization.json \
   /path/to/gui_repo/models/unet_60m_normalization.json
```

---

## If Files Are Missing

### SVGP Model

If the SVGP files don't exist, they need to be trained:

```bash
# Run HPO experiment (Phase 3)
bash hpc/exp3_hpo/run_exp3.sh training

# Or train specific config locally
python experiments/exp3_hpo/train_gp_hpo.py \
    --dataset optimized \
    --num-inducing 2000 \
    --kmeans-init \
    --data-dir results/exp1_gp_training_data/training_datasets \
    --output-dir results/exp3_hpo/hyperparameterization \
    --replicate 1
```

Training time: ~30 minutes on CPU, ~10 minutes on GPU

### U-Net Model

If the U-Net files don't exist, they need to be trained:

```bash
# Run U-Net experiment (Experiment 5)
bash hpc/exp5_unet/submit_unet_training.sh

# Or train locally (requires spatial data)
python experiments/exp5_unet/train_unet_klam.py \
    --data-dir results/exp1_gp_training_data/sail_data \
    --output-dir results/exp5_unet/training_results \
    --parcel-size 27 \
    --max-epochs 200 \
    --batch-size 32
```

Training time: ~2 hours on NVIDIA A100

**Note**: U-Net training requires spatial KLAM_21 data generated with `--collect-spatial-data` flag.

---

## Verifying Files

### Check File Sizes

```bash
ls -lh models/

# Expected output:
# svgp_60m.pth                 ~50 MB
# svgp_60m_normalization.json  ~2 KB
# unet_60m.pth                 ~50 MB  
# unet_60m_normalization.json  ~5 KB
```

### Test Loading

```python
import torch
import json

# Test SVGP
checkpoint = torch.load('models/svgp_60m.pth', weights_only=False)
print(f"SVGP inducing points: {checkpoint['num_inducing']}")
print(f"SVGP input dim: {checkpoint['input_dim']}")

with open('models/svgp_60m_normalization.json') as f:
    svgp_norm = json.load(f)
print(f"SVGP train_y_mean: {svgp_norm['train_y_mean']:.2f}")

# Test U-Net
checkpoint = torch.load('models/unet_60m.pth', weights_only=False)
print(f"U-Net config: {checkpoint['config']}")

with open('models/unet_60m_normalization.json') as f:
    unet_norm = json.load(f)
print(f"U-Net input channels: {list(unet_norm['input'].keys())}")
print(f"U-Net output channels: {list(unet_norm['output'].keys())}")
```

**Expected output**:
```
SVGP inducing points: 2000
SVGP input dim: 62
SVGP train_y_mean: 45.67
U-Net config: {'in_channels': 3, 'out_channels': 6, ...}
U-Net input channels: ['terrain', 'buildings', 'landuse']
U-Net output channels: ['Ex', 'Hx', 'uq', 'vq', 'uz', 'vz']
```

---

## Future: Multi-Parcel-Size Models

When models for additional parcel sizes (33m, 39m, ..., 99m) become available:

### File Naming Convention
```
models/
├── svgp_60m.pth
├── svgp_60m_normalization.json
├── svgp_33m.pth              ← New
├── svgp_33m_normalization.json
├── svgp_39m.pth              ← New
├── svgp_39m_normalization.json
...
├── unet_60m.pth
├── unet_60m_normalization.json
├── unet_33m.pth              ← New
├── unet_33m_normalization.json
...
```

### Auto-Detection

The `create_evaluator()` function will automatically detect available models:

```python
from model_evaluator import create_evaluator

# Will use svgp_51m.pth if available
evaluator = create_evaluator('svgp', parcel_size=51)

# Will raise FileNotFoundError if svgp_51m.pth doesn't exist
```

---

## Alternative: Multi-Scale U-Net (Future)

**Experiment 7** is developing a single U-Net that handles all parcel sizes:

```
models/
├── unet_multiscale.pth           ← One model for all sizes
└── unet_multiscale_normalization.json
```

This will reduce storage from ~650 MB (13 models) to ~50 MB (1 model).

---

## Troubleshooting

### "File not found" during copy
**Problem**: Results directories don't exist yet  
**Solution**: Run experiments first or download from HPC cluster

### "Model architecture mismatch"
**Problem**: Model file from wrong experiment  
**Solution**: Verify you're copying from correct results/ subdirectory

### "Normalization file missing"
**Problem**: Forgot to copy normalization.json  
**Solution**: Both .pth AND .json files are required

### "Models give poor predictions"
**Problem**: Using model trained on wrong data  
**Solution**: Ensure using models from `dataset_optimized` (not `dataset_random`)

---

## Model Provenance

### SVGP Model
- **Experiment**: exp3_hpo (Hyperparameter Optimization)
- **Training data**: ~26K samples from SAIL archives (exp1)
- **Configuration**: 2000 inducing points, K-means init, Matérn 2.5 ARD kernel
- **Performance**: R² = 0.946, Spearman ρ = 0.97
- **Training time**: ~30 minutes
- **Model size**: ~50 MB

### U-Net Model
- **Experiment**: exp5_unet (U-Net Surrogate Training)
- **Training data**: ~27K spatial samples from SAIL archives
- **Architecture**: Small U-Net, 64 base channels, depth=4, ResNet encoder
- **Performance**: R² = 0.997, MAE = 0.021
- **Training time**: ~1.3 hours on NVIDIA A100
- **Model size**: ~50 MB

---

## Contact

Questions about model files? See:
- `EXPERIMENTS.md` - Experiment descriptions
- `TECHNICAL.md` - Model architectures
- `experiments/exp3_hpo/train_gp_hpo.py` - SVGP training code
- `experiments/exp5_unet/train_unet_klam.py` - U-Net training code
