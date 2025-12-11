# Implementation Checklist

Use this checklist to systematically integrate the surrogate models into the OpenSKIZZE GUI.

---

## Phase 1: Setup & Verification (30 minutes)

### ☐ 1.1 Copy Integration Package
```bash
# From optimization repository
cd /path/to/openskizze-klam21-optimization
cp -r GUI_INTEGRATION_PACKAGE /path/to/gui_repo/openskizze_optimization/
```

### ☐ 1.2 Copy Model Files
```bash
# Copy trained models (adapt paths to your HPC results)
cp results/exp3_hpo/best_models/dataset_optimized_numind2000_kmeansinit/*.pth \
   /path/to/gui_repo/models/svgp_27m.pth

cp results/exp3_hpo/best_models/dataset_optimized_numind2000_kmeansinit/*normalization.json \
   /path/to/gui_repo/models/svgp_27m_normalization.json

cp results/exp5_unet/training_results/best_model.pth \
   /path/to/gui_repo/models/unet_27m.pth

cp results/exp5_unet/training_results/normalization.json \
   /path/to/gui_repo/models/unet_27m_normalization.json
```

### ☐ 1.3 Install Dependencies
```bash
# Activate your GUI environment
conda activate gui_env  # or your GUI environment

# Install with mamba (faster than conda)
mamba install torch>=2.0.0 gpytorch>=1.11 numba>=0.57.0
```

### ☐ 1.4 Verify Files
```bash
# Check package structure
ls openskizze_optimization/
# Expected: svgp.py, unet.py, model_evaluator.py, fast_encoding.py, *.yml

# Check models
ls models/
# Expected: svgp_27m.pth, unet_27m.pth, *_normalization.json (4 files total)
```

---

## Phase 2: Integration Testing (45 minutes)

### ☐ 2.1 Test Model Loading
Create `test_models.py`:
```python
import sys
sys.path.insert(0, 'openskizze_optimization')

from pathlib import Path
from model_evaluator import create_evaluator

# Test SVGP
try:
    evaluator = create_evaluator('svgp', parcel_size=27, models_dir=Path('models'), device='cpu')
    print("✓ SVGP model loaded")
except Exception as e:
    print(f"✗ SVGP failed: {e}")

# Test U-Net
try:
    evaluator = create_evaluator('unet', parcel_size=27, models_dir=Path('models'), device='cpu')
    print("✓ U-Net model loaded")
except Exception as e:
    print(f"✗ U-Net failed: {e}")

# Test Hybrid
try:
    evaluator = create_evaluator('hybrid', parcel_size=27, models_dir=Path('models'), device='cpu')
    print("✓ Hybrid evaluator created")
except Exception as e:
    print(f"✗ Hybrid failed: {e}")
```

Run:
```bash
python test_models.py
```

**Expected output**:
```
✓ SVGP model loaded
✓ U-Net model loaded
✓ Hybrid evaluator created
```

### ☐ 2.2 Test Evaluation Speed
Create `test_speed.py`:
```python
import sys
sys.path.insert(0, 'openskizze_optimization')

import time
import numpy as np
from pathlib import Path
from model_evaluator import create_evaluator

device = 'cuda'  # or 'cpu'
model_type = 'unet'  # or 'svgp' or 'hybrid'

evaluator = create_evaluator(model_type, parcel_size=27, models_dir=Path('models'), device=device)

# Generate random genomes
n_samples = 1024
genomes = np.random.randn(n_samples, 60)
parcel_sizes = np.full(n_samples, 27, dtype=np.float32)

# Warmup (JIT compilation)
_ = evaluator.evaluate(genomes[:32], parcel_sizes[:32])

# Benchmark
start = time.time()
results = evaluator.evaluate(genomes, parcel_sizes)
elapsed = time.time() - start

print(f"Evaluated {n_samples} genomes in {elapsed:.3f}s")
print(f"Speed: {elapsed/n_samples*1000:.2f} ms/genome")
print(f"Throughput: {n_samples/elapsed:.1f} genomes/sec")
```

**Expected performance**:
- CPU: ~5-10 ms/genome
- GPU: ~1-3 ms/genome

### ☐ 2.3 Test Feature Consistency
Create `test_features.py`:
```python
import sys
sys.path.insert(0, 'openskizze_optimization')

import numpy as np
from fast_encoding import NumbaFastEncoding

# Test single genome
encoding = NumbaFastEncoding(parcel_size=27)
genome = np.random.randn(60)
parcel_size = 27

heightmap, features = encoding.express_and_features(genome, parcel_size)

print(f"Heightmap shape: {heightmap.shape}")
print(f"Features shape: {features.shape}")
print(f"Features: GRZ={features[0]:.3f}, GFZ={features[1]:.3f}, AvgHeight={features[2]:.1f}m")

# Test batch
n_samples = 100
genomes = np.random.randn(n_samples, 60)
parcel_sizes = np.full(n_samples, 27, dtype=np.float32)

heightmaps, features_batch = encoding.express_and_features_batch(genomes, parcel_sizes)

print(f"\nBatch heightmaps shape: {heightmaps.shape}")
print(f"Batch features shape: {features_batch.shape}")
print(f"Feature ranges:")
for i, name in enumerate(['GRZ', 'GFZ', 'AvgH', 'VarH', 'AvgD', 'Count', 'Comp', 'Park']):
    print(f"  {name}: [{features_batch[:, i].min():.2f}, {features_batch[:, i].max():.2f}]")
```

**Expected**: All features within reasonable ranges (see `domain_cfg.yml`).

---

## Phase 3: GUI Code Modification (1-2 hours)

### ☐ 3.1 Add Model Selection UI

**Location**: Your GUI's optimization setup dialog/panel

```python
# Add dropdown/radio buttons for model selection
model_options = {
    'SVGP (Fast, Uncertainty)': 'svgp',
    'U-Net (Most Accurate)': 'unet',
    'Hybrid (Accuracy + Exploration)': 'hybrid'
}

# Add slider for UCB lambda (only for SVGP/Hybrid)
ucb_lambda_slider = Slider(min=0.0, max=5.0, value=1.0, step=0.1)
ucb_lambda_slider.visible = (selected_model in ['svgp', 'hybrid'])
```

### ☐ 3.2 Check Available Models

**Location**: Before optimization starts

```python
from pathlib import Path

def get_available_models(parcel_size: int) -> list:
    available = []
    models_dir = Path('models')
    
    if (models_dir / f'svgp_{parcel_size}m.pth').exists():
        available.append('svgp')
    if (models_dir / f'unet_{parcel_size}m.pth').exists():
        available.append('unet')
    if len(available) == 2:
        available.append('hybrid')
    
    return available

# Use in GUI
available = get_available_models(parcel_size)
if not available:
    show_warning(f"No models for {parcel_size}×{parcel_size}m. Using KLAM_21 (slow).")
    use_surrogate = False
else:
    use_surrogate = True
    model_dropdown.options = {k: v for k, v in model_options.items() if v in available}
```

### ☐ 3.3 Replace KLAM Evaluator

**Location**: Your MAP-Elites optimization function

**OLD CODE** (find this pattern):
```python
# Somewhere in your MAP-Elites loop
from domain_description.evaluation_klam import eval_multiple

for generation in range(n_generations):
    genomes = emitter.ask()
    objectives = eval_multiple(genomes, config_environment)  # ← SLOW
    features = calculate_planning_features(heightmaps)
    archive.add(genomes, objectives, features)
```

**NEW CODE**:
```python
from openskizze_optimization.model_evaluator import create_evaluator

# Initialize evaluator ONCE at start
if use_surrogate:
    evaluator = create_evaluator(
        model_type=selected_model,
        parcel_size=parcel_size,
        models_dir=Path('models'),
        device='cuda' if torch.cuda.is_available() else 'cpu',
        ucb_lambda=ucb_lambda
    )
else:
    evaluator = None  # Use KLAM_21

# In MAP-Elites loop
for generation in range(n_generations):
    genomes = emitter.ask()
    
    if evaluator is not None:
        # Fast surrogate evaluation
        results = evaluator.evaluate(genomes, parcel_sizes)
        objectives = results['objectives']
        features = results['features']
    else:
        # Slow KLAM_21 evaluation (fallback)
        objectives = eval_multiple(genomes, config_environment)
        features = calculate_planning_features(heightmaps)
    
    archive.add(genomes, objectives, features)
```

### ☐ 3.4 Update Archive Metadata

**Location**: Archive cell storage

```python
# Store model metadata with each solution
archive.add(
    solution=genome,
    objective=objective,
    measures=features,
    metadata={
        'model_type': selected_model,
        'ucb_lambda': ucb_lambda,
        'uncertainty': results.get('uncertainties', [None])[i],
        'timestamp': time.time()
    }
)
```

---

## Phase 4: End-to-End Testing (1 hour)

### ☐ 4.1 Short Optimization Run

```python
# Run 100 generations with each model
for model_type in ['svgp', 'unet', 'hybrid']:
    print(f"\nTesting {model_type}...")
    
    evaluator = create_evaluator(model_type, parcel_size=27, device='cuda')
    archive = run_mapelites(evaluator, generations=100)
    
    coverage = len(archive) / archive.capacity * 100
    qd_score = archive.stats.obj_sum
    
    print(f"  Coverage: {coverage:.2f}%")
    print(f"  QD Score: {qd_score:.1f}")
    print(f"  Archive size: {len(archive)}")
```

**Expected**:
- Coverage: 0.05-0.2% (100 gens is short)
- Archive size: 200-800 solutions
- QD score: Positive value

### ☐ 4.2 Verify Feature Distributions

```python
# After optimization, check feature distributions
features_data = archive.data(fields=['measures'])

import matplotlib.pyplot as plt
fig, axes = plt.subplots(2, 4, figsize=(16, 8))
feature_names = ['GRZ', 'GFZ', 'AvgH', 'VarH', 'AvgD', 'Count', 'Comp', 'Park']

for i, (ax, name) in enumerate(zip(axes.flat, feature_names)):
    ax.hist(features_data[:, i], bins=50)
    ax.set_title(name)
    ax.set_xlabel('Value')
    ax.set_ylabel('Count')

plt.tight_layout()
plt.savefig('feature_distributions.png')
```

**Check**: Features should span reasonable ranges (not all clustered at one value).

### ☐ 4.3 Performance Benchmark

```python
import time

# 1000 generations benchmark
start = time.time()
archive = run_mapelites(evaluator, generations=1000)
elapsed = time.time() - start

print(f"\n1000 generations completed in: {elapsed/60:.1f} minutes")
print(f"Expected:")
print(f"  SVGP: ~3 min")
print(f"  U-Net: ~5 min")
print(f"  Hybrid: ~6 min")
print(f"  KLAM_21 (old): ~58 hours")
```

---

## Phase 5: Production Deployment (30 minutes)

### ☐ 5.1 Add User Documentation

Update your GUI's help/documentation:
```
Optimization Models:
- SVGP: Fast predictions with uncertainty estimates. Use for exploration.
- U-Net: Highest accuracy (99.7%). Use for production optimization.
- Hybrid: Combines U-Net accuracy with SVGP uncertainty. Best quality.

UCB Lambda (λ):
- 0.0: Pure exploitation (greedy)
- 1.0: Balanced exploration-exploitation (recommended)
- 5.0: Maximum exploration (diverse archive)
```

### ☐ 5.2 Add Progress Indicators

```python
# Update GUI progress bar
progress_callback(
    generation=gen,
    total=total_gens,
    coverage=coverage,
    qd_score=qd_score,
    eval_time=eval_time
)
```

### ☐ 5.3 Add Error Handling

```python
try:
    evaluator = create_evaluator(...)
except FileNotFoundError as e:
    show_error(f"Model files missing: {e}\nPlease download models first.")
    return
except RuntimeError as e:
    if 'CUDA out of memory' in str(e):
        show_warning("GPU memory full. Switching to CPU (slower).")
        evaluator = create_evaluator(..., device='cpu')
    else:
        raise
```

### ☐ 5.4 Add Model Info Display

```python
# Show model info to user
model_info = {
    'svgp': "SVGP: R²=0.946, Speed=2ms, Uncertainty=Yes",
    'unet': "U-Net: R²=0.997, Speed=2ms, Uncertainty=No",
    'hybrid': "Hybrid: R²=0.997, Speed=3ms, Uncertainty=Yes"
}

info_label.text = model_info[selected_model]
```

---

## Phase 6: Validation & Quality Control (1 hour)

### ☐ 6.1 Compare with KLAM_21

```python
# Take 10 random solutions from archive
solutions = archive.sample(10)

# Evaluate with surrogate
surrogate_objectives = evaluator.evaluate(solutions['genomes'], solutions['parcel_sizes'])['objectives']

# Evaluate with KLAM_21
from domain_description.evaluation_klam import eval_multiple
klam_objectives = eval_multiple(solutions['genomes'], config_environment)

# Compare
from scipy.stats import spearmanr, pearsonr
spearman_rho = spearmanr(surrogate_objectives, klam_objectives)[0]
pearson_r = pearsonr(surrogate_objectives, klam_objectives)[0]

print(f"Validation (n=10):")
print(f"  Spearman ρ: {spearman_rho:.3f}")
print(f"  Pearson R: {pearson_r:.3f}")
print(f"  Expected: ρ > 0.90, R > 0.85")
```

### ☐ 6.2 Archive Quality Metrics

```python
# Compute QD metrics
coverage = len(archive) / archive.capacity * 100
qd_score = archive.stats.obj_sum
max_fitness = archive.stats.obj_max
mean_fitness = archive.stats.obj_mean

print(f"\nArchive Quality (1000 gens):")
print(f"  Coverage: {coverage:.2f}%")
print(f"  QD Score: {qd_score:.1f}")
print(f"  Max Fitness: {max_fitness:.2f}")
print(f"  Mean Fitness: {mean_fitness:.2f}")
```

### ☐ 6.3 Visual Inspection

```python
# Visualize top solutions
from pyribs.visualize import grid_archive_heatmap

fig, ax = plt.subplots(figsize=(10, 8))
grid_archive_heatmap(archive, ax=ax)
ax.set_title(f'{model_type.upper()} Archive (1000 gens)')
plt.savefig(f'archive_{model_type}.png')

# Render top 5 building layouts
top_elites = archive.retrieve([0.1, 0.2, 0.3, 0.4, 0.5])
for i, elite in enumerate(top_elites):
    render_layout(elite['solution'], filename=f'top_{i+1}.png')
```

---

## Completion Checklist

### Core Integration
- ☐ Model files copied and verified
- ☐ Dependencies installed
- ☐ Models load without errors
- ☐ Evaluation speed acceptable (<5ms/genome)
- ☐ Features calculated correctly
- ☐ GUI modified to use evaluators
- ☐ Model selection UI implemented

### Testing
- ☐ Short optimization run completes
- ☐ Archive coverage reasonable (>0.1%)
- ☐ Features span expected ranges
- ☐ Performance meets benchmarks
- ☐ Validation against KLAM_21 (ρ > 0.90)

### Production
- ☐ Error handling implemented
- ☐ User documentation updated
- ☐ Progress indicators working
- ☐ Model info displayed
- ☐ Graceful fallback to KLAM_21

### Quality Assurance
- ☐ Visual inspection of archive
- ☐ Top solutions rendered
- ☐ QD metrics logged
- ☐ No memory leaks (long runs)
- ☐ GPU/CPU switching works

---

## Success Criteria

✅ **Integration Successful If**:
1. Models load in <5 seconds
2. Evaluation speed: 1-5 ms/genome (GPU) or 5-10 ms/genome (CPU)
3. 1000 generations complete in <10 minutes (vs 58 hours with KLAM_21)
4. Archive coverage >0.1% after 1000 gens
5. Validation correlation: Spearman ρ > 0.90
6. No crashes during 10K generation run
7. Top solutions visually reasonable

---

## Next Steps After Integration

1. **Train models for more parcel sizes** (33m, 39m, ..., 99m)
2. **Implement validation mode** (periodically verify with KLAM_21)
3. **Add archive export** (CSV, JSON) for analysis
4. **Implement multi-scale U-Net** (one model for all sizes)
5. **Add real-time visualization** (archive heatmap updates)

---

**Questions or Issues?**

Refer to:
- `INTEGRATION_PROMPT.md` - Detailed documentation
- `experiments/exp6_qd_comparison/run_mapelites_offline.py` - Reference implementation
- `EXPERIMENTS.md` - Model performance details
