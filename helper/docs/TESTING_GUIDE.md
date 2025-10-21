# Quick Testing Guide

## How to Test the Performance Optimizations

### 1. Start the Application
```bash
cd /home/alex/Documents/_cloud/Funded_Projects/OpenSKIZZE/code/openskizze
python run.py
```

### 2. What to Look For

#### Console Output
You should see the new optimization messages:
```
[OPTIMIZATION] Pre-rotating environment for 15-30x rotation speedup...
[OPTIMIZATION] Environment prepared. Using optimized 2D rotation path.
```

#### Performance Comparison
**Before Optimizations:**
- Generation time: ~0.5-1.5 seconds per generation
- 1000 generations: 5-15 minutes total
- batch_size: 16

**After Optimizations:**
- Generation time: ~0.2-0.6 seconds per generation (2-3x faster)
- 1000 generations: 2-5 minutes total (2-3x faster)
- batch_size: 37

### 3. Run a Test Optimization

1. Open browser to `http://localhost:8050`
2. Go to **Step 1: Scope** - Load a test parcel
3. Go to **Step 2: Constraints** - Select optimization objective (Simple Porosity or Street Canyon)
4. Go to **Step 3: Optimize** - Click "Start Optimization"
5. Monitor console output for:
   - Optimization startup messages
   - Generation speed
   - Total completion time

### 4. Verify Results

✅ **Archive fills properly** (coverage > 0%, elites > 0)
✅ **Fitness values are reasonable** (0-1 range)
✅ **No errors in console**
✅ **Optimization completes faster** than before
✅ **Solutions visualize correctly** in Step 4

### 5. Performance Benchmarking

For detailed performance analysis:

```python
import time
import numpy as np
from backend.optimizer import run_qd_optimization
from backend.encoding import ParametricEncoding
from backend.config import QD_CONFIG

# Time a short optimization
qd_config = QD_CONFIG.copy()
qd_config['num_generations'] = 100  # Short test

start_time = time.time()
archive = run_qd_optimization(encoding_obj, env_config, qd_config)
end_time = time.time()

print(f"\n{'='*80}")
print(f"Performance Test Results")
print(f"{'='*80}")
print(f"Total time: {end_time - start_time:.2f} seconds")
print(f"Generations: {qd_config['num_generations']}")
print(f"Time per generation: {(end_time - start_time) / qd_config['num_generations']:.3f} seconds")
print(f"Archive stats: {archive.stats.num_elites} elites, {archive.stats.coverage * 100:.2f}% coverage")
print(f"{'='*80}\n")
```

### 6. Compare Against Baseline

**Expected Improvements:**
- ⚡ **2-3x overall speedup** (5-15 min → 2-5 min for 1000 generations)
- ⚡ **15-30x rotation speedup** (rotation overhead: 20% → 2%)
- ⚡ **Better CPU utilization** (batch_size: 16 → 37)
- ⚡ **Selective features** (1.1-1.3x when avoiding scipy operations)

### 7. Troubleshooting

**If optimization is still slow:**
1. Check console for "[OPTIMIZATION] Pre-rotating environment..." message
   - If missing, the optimized path is not being used
   
2. Verify wind direction is set before optimization starts
   - Pre-rotation requires wind_direction in env_config
   
3. Check CPU usage (should be high, ~80-95%)
   - If low, multiprocessing may not be working correctly

**If archive is empty:**
1. Check constraint violations in console output
2. Try relaxing constraints (max_height, min_distance)
3. Verify buildable area is reasonable

**If fitness values differ:**
1. Small numerical differences (<1%) are expected due to interpolation
2. Fitness landscape should be similar overall
3. Archive coverage should be comparable

### 8. Reverting to Legacy Mode (if needed)

The optimizations are backwards compatible. To force legacy 3D rotation:

```python
# In backend/optimizer.py, comment out:
# env_config = prepare_rotated_environment(env_config)
```

Or remove 'heightmap_2d_env_rotated' from env_config before evaluation.

---

## Expected Test Results

✅ **Startup:** New optimization messages appear
✅ **Speed:** 2-3x faster than before
✅ **Quality:** Same or better archive coverage
✅ **Stability:** No errors or crashes
✅ **Compatibility:** All features work as before

**Test Status:** Ready for validation
**Next Steps:** Run real optimization and measure actual speedup
