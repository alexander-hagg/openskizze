# KLAM_21 Surrogate Integration Plan for OpenSKIZZE

**Date**: November 12, 2025  
**Goal**: Integrate KLAM_21 cold airflow predictions via GP surrogate model into OpenSKIZZE GUI

---

## 1. Executive Summary

### Key Decisions
- ✅ **GP Input**: 62-dimensional (60-gene genome + parcel width + parcel height)
- ✅ **Training Strategy**: Separate SAIL runs per parcel size (15 sizes × 5k genomes = 75k KLAM runs)
- ✅ **GP Model**: GPyTorch with Matern kernel (scales to 100k+ samples, GPU acceleration)
- ✅ **Data Augmentation**: 30% random genomes for pessimistic prior (prevents overestimation)
- ✅ **Wind Direction**: Single direction (OpenSKIZZE rotates parcels to align with wind)
- ✅ **Timeline**: ~5-10 hours HPC walltime with 1280 cores

### Real NRW Parcel Statistics (from analysis)
- **Median size**: 27m × 16m (aspect ratio 1.53:1)
- **Range (5th-95th percentile)**: 6m - 144m width, 2m - 76m height
- **Coverage**: 10 square + 5 rectangular sizes cover 95% of urban plots

---

## 2. KLAM_21 Training Data Generation (Your Side)

### 2.1 Parcel Size Grid (Data-Driven)

**Square Parcels** (10 sizes):
```
25m, 30m, 35m, 45m, 55m, 65m, 80m, 95m, 120m, 145m
```
Coverage: 49% → 0.3% (small to large urban plots)

**Rectangular Parcels** (5 sizes):
```
30×20m, 35×20m, 45×30m, 50×25m, 65×45m
```
Coverage: Most common aspect ratios (1.5:1, 2:1)

**Total**: 15 parcel size variants

### 2.2 SAIL Training Strategy

#### Parallel SAIL Runs (One per Size)
```bash
# Submit 15 independent SAIL jobs to HPC

for size in 25 30 35 45 55 65 80 95 120 145; do
    sbatch run_sail_square.sh --width $size --height $size --genomes 5000
done

for size in "30,20" "35,20" "45,30" "50,25" "65,45"; do
    IFS=',' read -r w h <<< "$size"
    sbatch run_sail_rect.sh --width $w --height $h --genomes 5000
done
```

#### Per-Job Configuration
- **Genomes per size**: 5,000 elites (SAIL-optimized)
- **Additional random genomes**: 1,500 (Sobol sequence for pessimistic prior)
- **Total per size**: 6,500 KLAM_21 runs
- **Wind direction**: Single direction (e.g., 270° = West wind)
- **Output format**: `klam_size_{W}x{H}.npz` with:
  ```python
  {
      'genomes': (6500, 60),      # 60-gene solutions
      'widths': (6500,),          # Parcel width in meters
      'heights': (6500,),         # Parcel height in meters  
      'objectives': (6500,),      # KLAM_21 avg wind speed (m/s)
      'features': (6500, 8),      # Optional: GRZ, GSI, OSR, etc.
  }
  ```

#### Data Augmentation for Conservative Prior
```python
# In your SAIL code (run_sail.py):

# 1. Generate 5000 elites via SAIL
elites_genomes, elites_fitness = run_sail_qd(...)

# 2. Add 1500 random genomes (Sobol sequence)
from scipy.stats import qmc
sobol = qmc.Sobol(d=60, scramble=True)
random_genomes = sobol.random(1500) * 2 - 1  # Scale to [-1, 1]

# Evaluate random genomes with KLAM_21
random_fitness = [run_klam21(g, width, height) for g in random_genomes]

# 3. Combine for training dataset
all_genomes = np.vstack([elites_genomes, random_genomes])
all_fitness = np.concatenate([elites_fitness, random_fitness])

# Save
np.savez(f'klam_size_{width}x{height}.npz',
         genomes=all_genomes,
         widths=np.full(6500, width),
         heights=np.full(6500, height),
         objectives=all_fitness)
```

### 2.3 Compute Requirements

**Total KLAM Runs**: 15 sizes × 6,500 runs = **97,500 runs**

**HPC Resources**:
- Cores: 1280 parallel (10 nodes × 128 cores)
- Time per run: 5-10 minutes
- **Total walltime**: 6-12 hours (overnight job)

**Storage**: ~100MB per size × 15 = ~1.5GB total

---

## 3. GP Model Training (OpenSKIZZE Side)

### 3.1 New Module: `backend/klam_surrogate.py`

```python
"""
KLAM_21 Surrogate Model using Gaussian Process Regression.

Predicts cold airflow velocity based on:
- Genome (60 genes: 10 buildings × 6 parameters)
- Parcel dimensions (width, height in meters)
"""

import torch
import gpytorch
import numpy as np
from pathlib import Path
from typing import Tuple


class MultiscaleKLAMGP(gpytorch.models.ExactGP):
    """
    GPyTorch GP model with conservative prior for KLAM_21 surrogate.
    
    Input: [genome (60), parcel_width (1), parcel_height (1)] = 62 dims
    Output: KLAM_21 fitness (avg wind speed in m/s) + uncertainty
    """
    
    def __init__(self, train_x, train_y, likelihood):
        super().__init__(train_x, train_y, likelihood)
        
        # Conservative mean: Start at worst observed fitness
        self.mean_module = gpytorch.means.ConstantMean(
            constant_prior=gpytorch.priors.NormalPrior(
                loc=train_y.min().item(),
                scale=train_y.std().item()
            )
        )
        
        # Matern 2.5 kernel with ARD (separate lengthscale per dimension)
        self.covar_module = gpytorch.kernels.ScaleKernel(
            gpytorch.kernels.MaternKernel(
                nu=2.5,
                ard_num_dims=62,  # 60 genes + 2 size params
                lengthscale_constraint=gpytorch.constraints.Interval(0.01, 100.0)
            )
        )
        
    def forward(self, x):
        mean_x = self.mean_module(x)
        covar_x = self.covar_module(x)
        return gpytorch.distributions.MultivariateNormal(mean_x, covar_x)


def load_klam_dataset(data_dir: str = 'models/klam_data') -> Tuple[np.ndarray, np.ndarray]:
    """
    Load and combine all KLAM training datasets.
    
    Returns:
        X: (N, 62) array of [genome (60), width (1), height (1)]
        y: (N,) array of KLAM fitness values
    """
    data_path = Path(data_dir)
    all_X, all_y = [], []
    
    for npz_file in sorted(data_path.glob('klam_size_*.npz')):
        data = np.load(npz_file)
        
        genomes = data['genomes']  # (6500, 60)
        widths = data['widths']    # (6500,)
        heights = data['heights']  # (6500,)
        fitness = data['objectives']  # (6500,)
        
        # Combine into 62-dim input
        X = np.column_stack([genomes, widths, heights])
        
        all_X.append(X)
        all_y.append(fitness)
        
        print(f"Loaded {npz_file.name}: {len(fitness)} samples")
    
    X_combined = np.vstack(all_X)
    y_combined = np.concatenate(all_y)
    
    print(f"\nTotal training data: {len(y_combined):,} samples")
    print(f"Fitness range: {y_combined.min():.3f} - {y_combined.max():.3f} m/s")
    
    return X_combined, y_combined


def train_klam_gp(X: np.ndarray, y: np.ndarray, 
                  train_iterations: int = 100,
                  use_gpu: bool = True) -> Tuple[MultiscaleKLAMGP, gpytorch.likelihoods.GaussianLikelihood]:
    """
    Train GPyTorch model on KLAM dataset.
    
    Args:
        X: (N, 62) input array
        y: (N,) fitness array
        train_iterations: Number of optimization iterations
        use_gpu: Use CUDA if available
    
    Returns:
        Trained model and likelihood
    """
    device = torch.device('cuda' if use_gpu and torch.cuda.is_available() else 'cpu')
    print(f"Training on: {device}")
    
    # Convert to torch tensors
    train_x = torch.tensor(X, dtype=torch.float32).to(device)
    train_y = torch.tensor(y, dtype=torch.float32).to(device)
    
    # Normalize inputs (important for GP)
    train_x_mean = train_x.mean(dim=0)
    train_x_std = train_x.std(dim=0)
    train_x_normalized = (train_x - train_x_mean) / (train_x_std + 1e-8)
    
    # Initialize model
    likelihood = gpytorch.likelihoods.GaussianLikelihood().to(device)
    model = MultiscaleKLAMGP(train_x_normalized, train_y, likelihood).to(device)
    
    # Training mode
    model.train()
    likelihood.train()
    
    # Optimizer (Adam with learning rate scheduling)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.1)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=train_iterations)
    
    # Loss function
    mll = gpytorch.mlls.ExactMarginalLogLikelihood(likelihood, model)
    
    print(f"\nTraining GP for {train_iterations} iterations...")
    for i in range(train_iterations):
        optimizer.zero_grad()
        output = model(train_x_normalized)
        loss = -mll(output, train_y)
        loss.backward()
        optimizer.step()
        scheduler.step()
        
        if (i + 1) % 10 == 0:
            print(f"Iter {i+1}/{train_iterations} - Loss: {loss.item():.3f}")
    
    # Save normalization parameters
    model.train_x_mean = train_x_mean
    model.train_x_std = train_x_std
    
    print("✓ Training complete!")
    return model, likelihood


def save_klam_gp(model, likelihood, filepath: str = 'models/klam_gp_model.pth'):
    """Save trained GP model."""
    torch.save({
        'model_state_dict': model.state_dict(),
        'likelihood_state_dict': likelihood.state_dict(),
        'train_x_mean': model.train_x_mean,
        'train_x_std': model.train_x_std
    }, filepath)
    print(f"✓ Model saved to {filepath}")


def load_klam_gp(filepath: str = 'models/klam_gp_model.pth',
                 use_gpu: bool = True) -> Tuple[MultiscaleKLAMGP, gpytorch.likelihoods.GaussianLikelihood]:
    """Load pre-trained GP model."""
    device = torch.device('cuda' if use_gpu and torch.cuda.is_available() else 'cpu')
    
    checkpoint = torch.load(filepath, map_location=device)
    
    # Recreate model (need dummy data for initialization)
    dummy_x = torch.zeros((1, 62)).to(device)
    dummy_y = torch.zeros(1).to(device)
    
    likelihood = gpytorch.likelihoods.GaussianLikelihood().to(device)
    model = MultiscaleKLAMGP(dummy_x, dummy_y, likelihood).to(device)
    
    # Load state
    model.load_state_dict(checkpoint['model_state_dict'])
    likelihood.load_state_dict(checkpoint['likelihood_state_dict'])
    model.train_x_mean = checkpoint['train_x_mean']
    model.train_x_std = checkpoint['train_x_std']
    
    # Evaluation mode
    model.eval()
    likelihood.eval()
    
    print(f"✓ Model loaded from {filepath}")
    return model, likelihood


def predict_klam(model, likelihood, genome: np.ndarray, 
                 parcel_width_m: float, parcel_height_m: float,
                 return_uncertainty: bool = True) -> Tuple[float, float]:
    """
    Predict KLAM_21 fitness for a single solution.
    
    Args:
        model: Trained GP model
        likelihood: GP likelihood
        genome: (60,) genome array
        parcel_width_m: Parcel width in meters
        parcel_height_m: Parcel height in meters
        return_uncertainty: Return std deviation
    
    Returns:
        (mean, std) if return_uncertainty else mean
    """
    device = next(model.parameters()).device
    
    # Construct input
    x = np.concatenate([genome, [parcel_width_m, parcel_height_m]])
    x_tensor = torch.tensor(x, dtype=torch.float32).unsqueeze(0).to(device)
    
    # Normalize
    x_normalized = (x_tensor - model.train_x_mean) / (model.train_x_std + 1e-8)
    
    # Predict
    with torch.no_grad(), gpytorch.settings.fast_pred_var():
        pred = likelihood(model(x_normalized))
        mean = pred.mean.cpu().item()
        std = pred.stddev.cpu().item()
    
    return (mean, std) if return_uncertainty else mean


# Training script
if __name__ == "__main__":
    print("KLAM_21 GP Surrogate Training")
    print("="*60)
    
    # Load data
    X, y = load_klam_dataset('models/klam_data')
    
    # Train model
    model, likelihood = train_klam_gp(X, y, train_iterations=100, use_gpu=True)
    
    # Save model
    save_klam_gp(model, likelihood, 'models/klam_gp_model.pth')
    
    print("\n✓ Done! Model ready for OpenSKIZZE integration.")
```

### 3.2 Integration into `backend/evaluation.py`

Add KLAM surrogate objective:

```python
def compute_fitness_klam_surrogate(solution_genome: np.ndarray,
                                   parcel_width_m: float,
                                   parcel_height_m: float,
                                   klam_model,
                                   klam_likelihood) -> Tuple[float, float]:
    """
    Compute KLAM_21 fitness using GP surrogate.
    
    Returns:
        (fitness_mean, fitness_std): Predicted wind speed ± uncertainty
    """
    from backend.klam_surrogate import predict_klam
    
    mean, std = predict_klam(
        klam_model, klam_likelihood,
        solution_genome, parcel_width_m, parcel_height_m,
        return_uncertainty=True
    )
    
    return mean, std


# Update eval_solution() to handle KLAM objective
def eval_solution(solution, env_config):
    # ... existing code ...
    
    objective = env_config.get('objective_function', 'simple_porosity')
    
    if objective == 'simple_porosity':
        fitness = compute_fitness_simple_porosity(...)
        uncertainty = 0.0  # Deterministic
        
    elif objective == 'street_canyon':
        fitness = compute_fitness_street_canyon(...)
        uncertainty = 0.0
        
    elif objective == 'klam_surrogate':
        # Get parcel dimensions from env_config
        parcel_width = env_config['parcel_width_m']
        parcel_height = env_config['parcel_height_m']
        
        # Load GP model (cached in env_config)
        klam_model = env_config['klam_model']
        klam_likelihood = env_config['klam_likelihood']
        
        fitness, uncertainty = compute_fitness_klam_surrogate(
            solution, parcel_width, parcel_height,
            klam_model, klam_likelihood
        )
    
    # Store uncertainty for UI display
    return fitness, uncertainty
```

---

## 4. UI Integration

### 4.1 Step 2: Objective Selection (`pages/step2_constraints.py`)

Add KLAM option with warning:

```python
dbc.RadioItems(
    id='objective-selection',
    options=[
        {'label': T[lang]['OBJECTIVE_SIMPLE_POROSITY'], 'value': 'simple_porosity'},
        {'label': T[lang]['OBJECTIVE_STREET_CANYON'], 'value': 'street_canyon'},
        {'label': f"{T[lang]['OBJECTIVE_KLAM_SURROGATE']} 🧪", 'value': 'klam_surrogate'},
    ],
    value='simple_porosity'
),

# Conditional info panel for KLAM
dbc.Collapse(
    dbc.Alert([
        html.H5([
            html.I(className="bi bi-info-circle me-2"),
            T[lang]['KLAM_INFO_TITLE']
        ]),
        html.P(T[lang]['KLAM_INFO_DESC']),
        html.Ul([
            html.Li(T[lang]['KLAM_INFO_1']),  # "Based on 97,500 KLAM_21 simulations"
            html.Li(T[lang]['KLAM_INFO_2']),  # "Predicts cold air flow velocity (m/s)"
            html.Li(T[lang]['KLAM_INFO_3']),  # "Includes prediction uncertainty"
            html.Li(T[lang]['KLAM_INFO_4']),  # "Works for parcels 25-145m"
        ]),
        html.Hr(),
        html.Small([
            html.Strong(T[lang]['KLAM_WARNING']),
            " ",
            T[lang]['KLAM_WARNING_TEXT']  # "This is a surrogate model, not real KLAM_21"
        ], className='text-muted')
    ], color='info', className='mt-3'),
    id='klam-info-collapse',
    is_open=False
)
```

**Translations** (`backend/translation.py`):
```python
T['DE']['OBJECTIVE_KLAM_SURROGATE'] = "KLAM_21 Kaltluftströmung (Modell)"
T['EN']['OBJECTIVE_KLAM_SURROGATE'] = "KLAM_21 Cold Air Flow (Model)"

T['DE']['KLAM_INFO_TITLE'] = "Über KLAM_21 Surrogate"
T['EN']['KLAM_INFO_TITLE'] = "About KLAM_21 Surrogate"

T['DE']['KLAM_INFO_1'] = "Basiert auf 97.500 echten KLAM_21-Simulationen"
T['EN']['KLAM_INFO_1'] = "Based on 97,500 real KLAM_21 simulations"

# ... etc
```

### 4.2 Step 4: Analysis with Uncertainty (`pages/step4_analysis.py`)

Show uncertainty heatmap alongside fitness:

```python
# When KLAM objective is used:
if objective == 'klam_surrogate':
    # Create two heatmaps side-by-side
    
    # Left: Fitness (mean prediction)
    fig_fitness = create_archive_heatmap(
        archive_df, 
        metric='objective',
        title=T[lang]['KLAM_FITNESS_MAP']
    )
    
    # Right: Uncertainty (std deviation)
    fig_uncertainty = create_archive_heatmap(
        archive_df,
        metric='uncertainty',
        title=T[lang]['KLAM_UNCERTAINTY_MAP'],
        colorscale='Reds'  # Red = high uncertainty
    )
    
    return dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_fitness), width=6),
        dbc.Col(dcc.Graph(figure=fig_uncertainty), width=6)
    ])
```

### 4.3 Step 5/6: Solution Comparison with Confidence

Show ± uncertainty in solution cards:

```python
# Solution metric display
html.Div([
    html.Strong("KLAM_21 Fitness: "),
    html.Span(f"{fitness_mean:.2f} ± {fitness_std:.2f} m/s"),
    html.Small(f" (95% CI: [{fitness_mean - 1.96*fitness_std:.2f}, {fitness_mean + 1.96*fitness_std:.2f}])")
])
```

---

## 5. Model Loading Strategy

### Option A: Pre-trained Model (Recommended)

1. Train GP once on your machine/HPC after KLAM runs complete
2. Save `klam_gp_model.pth` (~50-100MB)
3. Ship with OpenSKIZZE in `models/` directory
4. Load on app startup:

```python
# In backend/config.py or optimization_process.py

KLAM_MODEL = None
KLAM_LIKELIHOOD = None

def load_klam_model_if_needed():
    global KLAM_MODEL, KLAM_LIKELIHOOD
    
    if KLAM_MODEL is None:
        model_path = 'models/klam_gp_model.pth'
        if Path(model_path).exists():
            from backend.klam_surrogate import load_klam_gp
            KLAM_MODEL, KLAM_LIKELIHOOD = load_klam_gp(model_path, use_gpu=False)
            print("✓ KLAM GP model loaded")
        else:
            print("⚠ KLAM model not found. KLAM objective disabled.")
```

### Option B: On-Demand Training (Development)

For testing before HPC run completes:
- Use synthetic data or small subset
- Train on first use (slow startup)

---

## 6. Validation Strategy

### 6.1 Hold-out Test Set (10%)

During training:
```python
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.1, random_state=42
)

# Train on X_train only
model, likelihood = train_klam_gp(X_train, y_train)

# Test on X_test
predictions = predict_batch(model, likelihood, X_test)
mse = np.mean((predictions - y_test)**2)
r2 = 1 - mse / np.var(y_test)

print(f"Test R²: {r2:.3f}")
print(f"Test RMSE: {np.sqrt(mse):.3f} m/s")
```

### 6.2 Size Interpolation Test

Test GP on unseen parcel size (e.g., 40m × 40m):
- Generate test genomes
- Predict with GP
- Compare to real KLAM_21 (run a few manually)

### 6.3 Uncertainty Calibration

Check if uncertainty estimates are well-calibrated:
```python
# Predictions on test set
means, stds = predict_batch(model, likelihood, X_test, return_std=True)

# Check if 95% of true values fall within ±1.96*std
in_ci = np.abs(y_test - means) <= 1.96 * stds
calibration = in_ci.mean()

print(f"95% CI coverage: {calibration:.1%}")  # Should be ~95%
```

---

## 7. Timeline & Milestones

### Week 1: SAIL Setup (Your Side)
- [ ] Modify SAIL code to accept parcel size parameters
- [ ] Implement Sobol random genome generation (30% of data)
- [ ] Test single KLAM run with size parameters
- [ ] Create HPC job submission scripts for 15 sizes

### Week 2: HPC Run (Your Side)
- [ ] Submit 15 parallel SAIL jobs
- [ ] Monitor progress (6-12 hour walltime)
- [ ] Validate output format (npz files)
- [ ] Transfer data to training machine

### Week 3: GP Training & OpenSKIZZE Integration (My Side)
- [ ] Create `backend/klam_surrogate.py` module
- [ ] Train GP model on combined dataset
- [ ] Validate test set performance (R² > 0.9 target)
- [ ] Save trained model
- [ ] Integrate into `backend/evaluation.py`

### Week 4: UI & Testing (My Side)
- [ ] Add KLAM objective to Step 2 UI
- [ ] Add uncertainty visualization to Step 4
- [ ] Update Step 5/6 comparison views
- [ ] Add bilingual translations
- [ ] Test with real user workflow

### Week 5: Validation & Refinement (Both)
- [ ] Run test optimizations with KLAM objective
- [ ] Compare archive quality to simple_porosity
- [ ] Check uncertainty calibration
- [ ] Performance tuning (prediction speed)
- [ ] Documentation updates

---

## 8. Success Criteria

- ✅ GP model achieves R² > 0.90 on test set
- ✅ Prediction speed < 5ms per solution (batch of 100)
- ✅ Uncertainty estimates are well-calibrated (95% CI coverage ~95%)
- ✅ KLAM objective generates non-empty QD archives
- ✅ UI clearly communicates surrogate model limitations
- ✅ Model works for parcels 25-145m (training range)

---

## 9. Future Enhancements (Post-MVP)

### Phase 2: ML Surrogate
- Replace GP with neural network (faster, scales to millions)
- Train on even larger dataset
- Support multiple wind directions

### Phase 3: Active Learning
- User selects promising solutions
- Run real KLAM_21 on selected solutions
- Retrain GP with new data
- Iterative refinement

### Phase 4: Multi-Objective
- Combine KLAM with simple_porosity
- Pareto front exploration
- Trade-off visualization

---

## 10. Contact & Questions

**Your Tasks**: SAIL setup, HPC runs, data generation  
**My Tasks**: GP training, OpenSKIZZE integration, UI  

**Next Steps**:
1. You: Implement SAIL modifications for multi-size support
2. You: Submit HPC job (overnight run)
3. Me: Start building `klam_surrogate.py` module (can use dummy data)
4. Both: Meet to validate dataset format after HPC run

---

**Ready to proceed? Let me know when your HPC run completes!** 🚀
