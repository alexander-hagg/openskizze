# Production Configuration Recommendation - OpenSKIZZE

## 🎯 Recommended Configuration

Based on comprehensive benchmarking with realistic batch sizes:

### Optimal Setup for Production

```python
# Configuration
USE_JIT = True
USE_SINGLE_THREADED = True  # For typical batch sizes (< 100)
WARM_UP_AT_STARTUP = True
BATCH_SIZE = 32-64  # Typical production range
```

## Why Single-Threaded?

### Multiprocessing Overhead Analysis

Multiprocessing adds significant overhead:
```
Fixed overhead per batch: ~20-35ms
  - Process spawning: 5-10ms
  - Data serialization: 10-20ms
  - IPC communication: 2-5ms
```

### Performance Comparison (Batch Size 32)

| Configuration | Time | Per Solution | Winner |
|---------------|------|--------------|--------|
| **Planning JIT Single** | 20.4 ms | 0.64 ms | ✅ **Winner** |
| **Planning JIT Multi** | 52.1 ms | 1.63 ms | ❌ 2.6× slower |

**Multiprocessing wastes 31.7ms on overhead!**

### Performance Comparison (Batch Size 64)

| Configuration | Time | Per Solution | Winner |
|---------------|------|--------------|--------|
| **Planning JIT Single** | 44.7 ms | 0.70 ms | ✅ **Winner** |
| **Planning JIT Multi** | 58.4 ms | 0.91 ms | ❌ 1.3× slower |

**Multiprocessing wastes 13.7ms on overhead!**

### Break-Even Point

```
Single-threaded wins when: batch_size < ~100
Multiprocessing wins when: batch_size > ~100

For typical batch sizes (32-64): Use single-threaded!
```

## Performance Metrics

### With JIT + Single-threaded (Batch Size 64)

```
Original features:  27.6 ms total (0.43 ms/solution)
Planning features:  44.7 ms total (0.70 ms/solution)

Speedup over no-JIT:
  Original: 1.25×
  Planning: 20.7× 🚀

Throughput:
  Original: 2,318 solutions/second
  Planning: 1,431 solutions/second
```

### Production Projection (50,000 evaluations)

```
Batch size: 64 solutions
Number of batches: 781

Single-threaded + JIT:
  Time per batch: 44.7 ms
  Total time: 34.9 seconds (~0.6 minutes) ✅

Multiprocessing + JIT:
  Time per batch: 58.4 ms  
  Total time: 45.6 seconds (~0.8 minutes)

Time saved with single-threaded: 10.7 seconds
```

## Implementation Guide

### 1. Add JIT Warm-up to app.py

```python
# In app.py or optimization_process.py

import numpy as np
from backend.evaluation import (
    calculate_all_features_original_jit,
    calculate_all_features_planning_jit
)

def warmup_jit_compilation():
    """
    Pre-compile all JIT functions at application startup.
    This is a one-time cost (~3 seconds) that eliminates compilation overhead.
    """
    print("🔥 Warming up JIT compilation...")
    
    # Create dummy data
    dummy_grid = np.zeros((30, 30), dtype=np.float32)
    dummy_mask = np.ones((30, 30), dtype=bool)
    dummy_area = 8100.0  # 30x30 grid with 3m pixels
    
    # Compile all JIT functions
    try:
        _ = calculate_all_features_original_jit(dummy_grid, dummy_mask, dummy_area)
        _ = calculate_all_features_planning_jit(dummy_grid, dummy_mask, dummy_area)
        print("✅ JIT compilation complete!")
    except Exception as e:
        print(f"⚠️  JIT compilation failed: {e}")
        print("   Falling back to non-JIT versions")

# Call at startup (before any optimization)
if __name__ == "__main__":
    warmup_jit_compilation()
    # ... rest of app initialization
```

### 2. Update evaluation.py to Export JIT Functions

```python
# In backend/evaluation.py

# Add at the top:
try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # Define dummy decorator
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# ... existing code ...

# Add JIT-optimized versions:

@njit(cache=True, nogil=True)
def _compute_svf_core_jit(heightmap, pixel_size, num_rays=16, sample_stride=5):
    """JIT-compiled SVF core (copy from benchmark)."""
    # ... implementation ...
    pass

def calculate_sky_view_factor_jit(heightmap, pixel_size, num_rays=16, sample_stride=5):
    """JIT-optimized Sky View Factor calculation."""
    if NUMBA_AVAILABLE:
        return _compute_svf_core_jit(heightmap, pixel_size, num_rays, sample_stride)
    else:
        return calculate_sky_view_factor(heightmap, pixel_size, num_rays, sample_stride)

# ... similar for other JIT functions ...

def calculate_all_features_planning_jit(heightmap, buildable_mask, buildable_area):
    """
    Planning features with JIT optimization (hybrid approach).
    Uses JIT for expensive computations, scipy for labeling.
    """
    if not NUMBA_AVAILABLE:
        return calculate_all_features_planning(heightmap, buildable_mask, buildable_area)
    
    # ... JIT-optimized implementation (copy from benchmark) ...
    pass

# Export JIT versions
__all__ = [
    'calculate_all_features',
    'calculate_all_features_planning',
    'calculate_all_features_original_jit',
    'calculate_all_features_planning_jit',
]
```

### 3. Update Optimization Loop

```python
# In backend/optimization_process.py or optimizer.py

from backend.evaluation import calculate_all_features_planning_jit

def evaluate_population(solutions, buildable_area, use_jit=True):
    """
    Evaluate a population of solutions.
    Uses single-threaded JIT for optimal performance with typical batch sizes.
    """
    results = []
    
    if use_jit:
        eval_func = calculate_all_features_planning_jit
    else:
        eval_func = calculate_all_features_planning
    
    # Single-threaded evaluation (optimal for batch < 100)
    for solution in solutions:
        features = eval_func(
            solution.heightmap,
            solution.buildable_mask,
            buildable_area
        )
        results.append(features)
    
    return np.array(results)

# Alternative: Batch evaluation with optional multiprocessing for large batches
def evaluate_population_adaptive(solutions, buildable_area, use_jit=True):
    """
    Adaptive evaluation: single-threaded for small batches, multiprocessing for large.
    """
    batch_size = len(solutions)
    
    if batch_size < 100:
        # Single-threaded (faster for small batches)
        return evaluate_population(solutions, buildable_area, use_jit)
    else:
        # Multiprocessing (faster for large batches)
        from multiprocessing import Pool
        
        if use_jit:
            eval_func = calculate_all_features_planning_jit
        else:
            eval_func = calculate_all_features_planning
        
        args = [(sol.heightmap, sol.buildable_mask, buildable_area) 
                for sol in solutions]
        
        with Pool() as pool:
            results = pool.starmap(eval_func, args)
        
        return np.array(results)
```

### 4. Configuration File (Optional)

```python
# config.py or settings.py

class OptimizationConfig:
    """Configuration for optimization process."""
    
    # JIT settings
    USE_JIT = True  # Enable Numba JIT compilation
    WARMUP_JIT_AT_STARTUP = True  # Pre-compile JIT functions
    
    # Evaluation settings
    EVALUATION_MODE = "auto"  # "single", "multi", or "auto"
    MULTIPROCESSING_THRESHOLD = 100  # Use MP only for batches > this size
    
    # Performance
    EXPECTED_SOLUTIONS_PER_SECOND = 1431  # With JIT single-threaded
    EXPECTED_TIME_PER_SOLUTION_MS = 0.70  # milliseconds
```

## Migration Checklist

- [ ] Copy JIT functions from `comprehensive_performance_benchmark.py` to `backend/evaluation.py`
- [ ] Add JIT warm-up function to `app.py`
- [ ] Call warm-up at application startup
- [ ] Update optimization loop to use JIT functions
- [ ] Use single-threaded evaluation (default)
- [ ] Test with small optimization run (100-1000 evaluations)
- [ ] Verify performance matches benchmark
- [ ] Optional: Add adaptive multiprocessing for large batches

## Testing the Implementation

```python
# Quick test script
import numpy as np
import time
from backend.evaluation import (
    calculate_all_features_planning,
    calculate_all_features_planning_jit
)

# Create test data
heightmap = np.random.rand(30, 30).astype(np.float32) * 20
heightmap[heightmap < 10] = 0
mask = np.ones((30, 30), dtype=bool)
area = 8100.0

# Test No-JIT
start = time.time()
for _ in range(100):
    result_no_jit = calculate_all_features_planning(heightmap, mask, area)
time_no_jit = time.time() - start

# Test JIT (warmed up)
_ = calculate_all_features_planning_jit(heightmap, mask, area)  # Warm up
start = time.time()
for _ in range(100):
    result_jit = calculate_all_features_planning_jit(heightmap, mask, area)
time_jit = time.time() - start

print(f"No JIT: {time_no_jit*1000:.1f} ms (100 evaluations)")
print(f"With JIT: {time_jit*1000:.1f} ms (100 evaluations)")
print(f"Speedup: {time_no_jit/time_jit:.1f}×")
print(f"Per solution: {time_jit*10:.2f} ms")

# Verify results match
np.testing.assert_allclose(result_no_jit, result_jit, rtol=1e-3)
print("✅ Results match!")
```

Expected output:
```
No JIT: 1448.0 ms (100 evaluations)
With JIT: 69.9 ms (100 evaluations)
Speedup: 20.7×
Per solution: 0.70 ms
✅ Results match!
```

## Expected Benefits

### Performance Improvements

```
Evaluation speed:
  Before (No JIT): 14.48 ms/solution
  After (JIT):     0.70 ms/solution
  Speedup:         20.7×

50,000 evaluations:
  Before: 724 seconds (12.1 minutes)
  After:  35 seconds (0.6 minutes)
  Time saved: 689 seconds (11.5 minutes)

Optimization throughput:
  Before: 69 solutions/second
  After:  1,431 solutions/second
  Increase: 20.7×
```

### User Experience

- ✅ Faster optimization runs (20× faster)
- ✅ More iterations in same time
- ✅ Better design space exploration
- ✅ Real-time feedback possible
- ✅ Interactive exploration feasible

## Troubleshooting

### If JIT compilation fails

```python
# Fallback gracefully
try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    warnings.warn("Numba not available. Using non-JIT versions (slower).")
```

### If performance doesn't match benchmark

1. **Check JIT warm-up**: Make sure functions are compiled before first use
2. **Verify Numba cache**: Check `__pycache__` for compiled functions
3. **Profile the code**: Use `line_profiler` to find bottlenecks
4. **Check data types**: Ensure NumPy arrays are `float32` or `float64`

### If results don't match

```python
# Compare outputs with tolerance
import numpy as np
np.testing.assert_allclose(result_no_jit, result_jit, rtol=1e-3, atol=1e-6)
```

If this fails, there's a bug in the JIT implementation. Debug by:
1. Testing each JIT function individually
2. Comparing intermediate results
3. Checking for type conversion issues

## Summary

### ✅ Recommended Configuration

```
Feature Set: Planning features
Optimization: JIT (hybrid with scipy)
Threading: Single-threaded
Batch Size: 32-64 (typical)
Warm-up: Yes (at startup)

Expected Performance:
- 0.70 ms per solution
- 1,431 solutions per second
- 50K evaluations in 35 seconds
```

### ❌ Not Recommended

```
❌ Multiprocessing for batch < 100 (overhead dominates)
❌ No JIT for planning features (20× slower)
❌ No warm-up (compilation overhead in first evaluations)
❌ Pure JIT without scipy (5× slower than hybrid)
```

### 🎯 Bottom Line

**Use JIT + Single-threaded for production.** This provides the best performance for typical batch sizes while keeping the implementation simple and avoiding multiprocessing overhead.

For 50,000 evaluations: **~35 seconds** with JIT vs **~724 seconds** without = **20.7× speedup!** 🚀
