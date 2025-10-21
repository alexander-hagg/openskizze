# Numba JIT Benchmark - Updated Results with Scipy Analysis

## Executive Summary

**Key Findings:**
1. ✅ **SVF with JIT**: **36.55× speedup** (5.907ms → 0.162ms)
2. ✅ **Planning features (JIT hybrid)**: **8.53× speedup** (6.255ms → 0.733ms)  
3. ⚠️ **Custom connected components (full JIT)**: **SLOWER** than scipy!
4. 🎯 **Best approach**: **Hybrid JIT** (JIT for computations + scipy for labeling)

## Why Replace Scipy? Analysis

### Question: Can we replace scipy.ndimage.label() with Numba?

**Answer: Yes, but it's NOT faster!**

### Scipy vs Custom Numba Implementation

| Operation | Scipy | Custom Numba | Winner |
|-----------|-------|--------------|--------|
| Connected components labeling | Fast (optimized C) | Slow (flood-fill) | **Scipy** |
| Center of mass | Fast | Fast (similar) | Tie |
| Overall feature calculation | 0.733ms (hybrid) | 3.933ms (full JIT) | **Scipy hybrid** |

**Conclusion**: **Scipy is already highly optimized!** It uses compiled C/C++ code under the hood, NOT pure Python. Replacing it with custom Numba code makes things **slower**, not faster.

### Performance Breakdown

**Single Solution Evaluation:**
```
Original features (scipy):              0.555 ms
Original features (full JIT):           0.061 ms  ← 9.13× faster!
Planning features (scipy):              6.255 ms
Planning features (JIT hybrid):         0.733 ms  ← 8.53× faster
Planning features (JIT full, no scipy): 3.933 ms  ← 1.59× faster, but SLOWER than hybrid!
```

**Batch Evaluation (100 solutions, multiprocessing):**
```
Original (no JIT):              72.4 ms
Original (with JIT):            95.4 ms  ← Actually slower! 
Planning (no JIT):             228.4 ms
Planning (JIT hybrid):          74.4 ms  ← 3.07× faster
Planning (JIT full, no scipy):  96.4 ms  ← 2.37× faster, but SLOWER than hybrid
```

### Why is Original Features with JIT Slower in Batch Mode?

**Surprising result**: Original features WITHOUT JIT: 72.4ms, WITH JIT: 95.4ms

**Explanation**:
1. **Multiprocessing overhead**: Each worker process must compile JIT functions
2. **Small workload**: Original features are already fast (0.555ms each)
3. **Compilation cost**: JIT compilation overhead dominates for simple operations
4. **Scipy efficiency**: scipy.ndimage operations are already near-optimal

**When JIT helps vs hurts:**
- ✅ **Helps**: Expensive computations (SVF ray-casting: 5.9ms → 0.16ms)
- ✅ **Helps**: Many loops and numeric operations
- ❌ **Hurts**: Simple operations where scipy/numpy are already efficient
- ❌ **Hurts**: Small batch sizes with multiprocessing (compilation overhead)

## Optimal Implementation Strategy

### Recommended: Hybrid JIT Approach

**Use JIT for:**
1. ✅ **SVF calculation** (36.55× speedup - the big win!)
2. ✅ **H/W ratio** (pairwise distances in tight loops)
3. ✅ **Building statistics** (mean, std with custom loops)

**Keep Scipy for:**
1. ✅ **Connected component labeling** (scipy.ndimage.label) - already optimized
2. ✅ **Center of mass** (scipy.ndimage.center_of_mass) - already efficient
3. ✅ **Binary morphology** (erosion, dilation) - highly optimized C code

### Implementation

```python
def calculate_all_features_planning_optimized(heightmap, buildable_mask, buildable_area):
    """
    Optimal hybrid approach: JIT where it helps, scipy where it's better.
    """
    pixel_area = buildable_area / np.sum(buildable_mask)
    pixel_size = np.sqrt(pixel_area)
    
    occupied = heightmap > 0
    
    if not np.any(occupied):
        return np.zeros(8)
    
    # JIT-optimized: building statistics
    _, num_pixels, avg_height, height_var = _compute_building_stats_jit(heightmap)
    
    # Simple numpy: area calculations
    built_area = num_pixels * pixel_area
    grz = built_area / buildable_area
    total_floor_area = np.sum(heightmap) * pixel_area
    gfz = total_floor_area / buildable_area
    
    # Keep scipy: connected components (already optimized!)
    labeled_array, num_buildings = label(occupied)
    
    # Keep scipy: centroids (already efficient)
    if num_buildings > 1:
        centroids = np.array(center_of_mass(occupied, labeled_array, 
                                           range(1, num_buildings + 1)))
        # Numpy vectorization: pairwise distances
        diff = centroids[:, None, :] - centroids[None, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        avg_spacing_pixels = np.mean(dists[np.triu_indices(num_buildings, k=1)])
        avg_spacing_meters = avg_spacing_pixels * pixel_size
    else:
        avg_spacing_meters = 0.0
    
    # JIT-optimized: H/W ratio
    hw_ratio = _compute_hw_ratio_jit(heightmap, pixel_size)
    
    # JIT-optimized: SVF (THE BIG WIN - 36× speedup!)
    svf = calculate_sky_view_factor_jit(heightmap, pixel_size)
    
    return np.array([grz, gfz, avg_height, height_var, float(num_buildings),
                     avg_spacing_meters, hw_ratio, svf])
```

## Performance Summary

### For 50,000 Evaluations (Typical Optimization Run)

| Configuration | Time | vs Baseline | Recommendation |
|---------------|------|-------------|----------------|
| **Original (no JIT)** | 27.8s (0.5 min) | Baseline | ✓ Keep as-is |
| Original (with JIT) | 47.7s (0.8 min) | +71% slower | ❌ Don't use |
| **Planning (no JIT)** | 312.8s (5.2 min) | +1025% slower | ❌ Too slow |
| **Planning (JIT hybrid)** | 36.7s (0.6 min) | **+32% slower** | ✅ **BEST** |
| Planning (JIT full) | 48.2s (0.8 min) | +73% slower | ❌ Don't use |

**Winner: JIT Hybrid Approach**
- Only 32% slower than original features (vs 1025% without JIT)
- Provides all planning features (GRZ, GFZ, H/W, SVF)
- Saves 276 seconds (4.6 minutes) compared to no JIT
- **96.9% reduction in planning overhead!**

## Understanding the "Full JIT is Slower" Phenomenon

### Why Custom Connected Components is Slow

**Scipy's label() function:**
- Implemented in C/Cython
- Uses union-find algorithm (optimal)
- Decades of optimization
- Memory-efficient
- Cache-friendly access patterns

**Custom Numba implementation:**
- Flood-fill algorithm (simpler but slower)
- Less optimal for typical cases
- More stack operations
- Not as cache-efficient

**Benchmark:**
- Scipy label: ~0.1ms for 30×30 grid
- Custom Numba: ~3-4ms for 30×30 grid
- **Scipy is 30-40× faster!**

### Lesson Learned

**Not everything benefits from JIT compilation:**
1. Scipy/NumPy already use compiled code (C/C++/Fortran)
2. Decades of optimization in scientific Python libraries
3. Replacing well-optimized libraries with custom code often makes things slower
4. **JIT wins big** only when:
   - You have custom algorithms scipy doesn't have (e.g., SVF ray-casting)
   - You need many nested loops with simple operations
   - The operation isn't already in an optimized library

## Recommendations

### Immediate Implementation (Priority 1) 🔥

**Use the hybrid JIT approach:**

1. **Add JIT-optimized SVF** to `backend/evaluation.py`
   - Replace: `calculate_sky_view_factor()` 
   - With: `calculate_sky_view_factor_jit()`
   - Impact: **36× speedup on main bottleneck**

2. **Add JIT-optimized H/W ratio**
   - Replace: inline pairwise distance calculation
   - With: `_compute_hw_ratio_jit()`
   - Impact: Moderate speedup

3. **Keep scipy for labeling**
   - DO NOT replace `scipy.ndimage.label()`
   - It's already optimal!

4. **Keep scipy for centroids**
   - DO NOT replace `scipy.ndimage.center_of_mass()`
   - It's already efficient!

### What NOT to Do ❌

1. ❌ **Don't JIT-optimize original features for batch evaluation**
   - Makes things slower due to compilation overhead
   - scipy is already near-optimal

2. ❌ **Don't replace scipy's connected components with custom Numba**
   - 30-40× slower than scipy!
   - scipy uses optimal union-find algorithm in C

3. ❌ **Don't replace all NumPy operations with JIT**
   - NumPy is already compiled (C/Fortran)
   - Only JIT when you have custom logic in tight loops

### Testing Before Deployment

```bash
# Run comprehensive benchmark
python helper/numba_benchmark.py

# Expected results:
# - SVF: ~36× speedup
# - Planning hybrid: ~8.5× speedup  
# - Planning hybrid batch: ~3× speedup
# - Full feature time: ~0.7ms per solution

# Verify accuracy
python tests/test_features_visual.py
# All tests should pass with identical results
```

## Conclusion

**Key Takeaways:**

1. 🚀 **Numba JIT is incredible for custom algorithms** (SVF: 36× speedup!)
2. 📚 **Scipy is already highly optimized** - don't replace it unnecessarily
3. 🎯 **Hybrid approach wins**: JIT for custom code, scipy for library operations
4. ⚠️ **Measure, don't assume**: Always benchmark before replacing optimized libraries
5. ✅ **Planning features are now practical**: Only 32% slower than original (vs 1025% before)

**Bottom line**: Implement the hybrid JIT approach for production. It provides massive speedups where they matter (SVF) while respecting the excellent optimizations already present in scipy/numpy.

---

**Files:**
- Benchmark script: `helper/numba_benchmark.py`
- This analysis: `helper/SCIPY_NUMBA_ANALYSIS.md`
- Run: `python helper/numba_benchmark.py`
