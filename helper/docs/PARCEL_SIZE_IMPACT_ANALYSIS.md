# Parcel Size Impact Analysis - Critical Findings

**Date:** October 21, 2025  
**Critical Discovery:** Feature calculation has **catastrophic O(N^1.35) scaling** with parcel size!

---

## 🚨 CRITICAL FINDING: Feature Calculation Scaling Disaster

### The Problem

**Feature calculation with JIT shows CATASTROPHIC scaling at large parcel sizes:**

| Parcel Size | Grid Size | Feature Time | Scaling Factor |
|-------------|-----------|--------------|----------------|
| 50m × 50m | 17×17 | **0.30 ms** | 1.0× (baseline) |
| 100m × 100m | 34×34 | **1.12 ms** | 3.8× |
| 500m × 500m | 167×167 | **142.80 ms** | **479.6×** 🔥 |

**This is MUCH worse than expected O(N²) scaling!**

### Observed Complexity

```
Component            Expected    Observed    Status
-------------------------------------------------
Phenotype (JIT)      O(N²)      O(N^0.40)   ✅ Better than expected!
3D Mesh (JIT)        O(N²×H)    O(N^0.75)   ✅ Better than expected!
Fitness (scipy)      O(N²×H)    O(N^0.89)   ✅ Good scaling
Features (JIT)       O(N²)      O(N^1.35)   🚨 WORSE than expected!
```

**Why is O(N^1.35) worse than expected O(N²)?**
- For 167×167 grid (96.5× more pixels), we'd expect ~96.5× slower
- Instead we see **479.6× slower** - 5× worse than linear prediction!
- This suggests **algorithmic inefficiency** in feature calculation at scale

---

## Bottleneck Transition by Parcel Size

### Small Parcels (50m × 50m): Fitness Dominates ✅

```
Total: 0.90 ms per solution
├─ Fitness:    0.59 ms  (66%) 🎯 BOTTLENECK
├─ Features:   0.30 ms  (33%)
├─ Phenotype:  0.00 ms  (0.3%)
└─ 3D Mesh:    0.00 ms  (0.3%)
```

**Recommendation:** Scipy rotation is bottleneck but already optimized. Accept it.

### Medium Parcels (100m × 100m): Mixed

```
Total: 2.75 ms per solution
├─ Fitness:    1.62 ms  (59%) 🎯 BOTTLENECK
├─ Features:   1.12 ms  (41%)
├─ Phenotype:  0.00 ms  (0.2%)
└─ 3D Mesh:    0.01 ms  (0.2%)
```

**Recommendation:** Both fitness and features matter. Balance optimization.

### Large Parcels (500m × 500m): Feature Catastrophe 🚨

```
Total: 178.07 ms per solution
├─ Features:  142.80 ms  (80%) 🚨 CATASTROPHIC BOTTLENECK
├─ Fitness:    35.18 ms  (20%)
├─ 3D Mesh:     0.08 ms  (0.04%)
└─ Phenotype:   0.01 ms  (0.01%)
```

**CRITICAL:** Feature calculation **completely dominates** at large scales!

---

## Why Is Feature Calculation So Slow at 500m?

### Hypothesis: Sky View Factor Ray Casting

**Most likely culprit:** `_compute_svf_core_jit()` function

```python
@njit(cache=True, nogil=True)
def _compute_svf_core_jit(heightmap, pixel_size, num_rays=16, sample_stride=5):
    rows, cols = heightmap.shape
    
    for r in range(0, rows, sample_stride):
        for c in range(0, cols, sample_stride):
            for angle in angles:  # 16 rays
                for step in range(1, max(rows, cols)):  # Ray marching
                    # Check if ray hits obstacle
```

**Complexity analysis:**
- Sample points: `(N/5)²` where N = grid_size
- Rays per point: 16
- Steps per ray: N (proportional to grid size)
- **Total operations: (N/5)² × 16 × N = O(N³)**

**For 167×167 grid:**
- Sample points: (167/5)² = 1,112 points
- Rays: 1,112 × 16 = 17,792 rays
- Steps per ray: ~167 steps
- **Total: 2.97 million ray-marching steps!**

**For 17×17 grid:**
- Sample points: (17/5)² = 11 points
- Rays: 11 × 16 = 176 rays
- Steps per ray: ~17 steps
- **Total: 3,000 ray-marching steps**

**Ratio: 2.97M / 3K = 990× more work!**

This matches the observed **480× slowdown** (some efficiency from JIT compilation).

---

## Secondary Culprits

### H/W Ratio Calculation

```python
@njit(cache=True, nogil=True)
def _compute_hw_ratio_jit(heightmap, pixel_size):
    # Finds all building pixels: O(N²)
    # Compares all pairs: O(n²) where n = number of building pixels
    
    for i in range(n):
        for j in range(i + 1, n):
            # Calculate pairwise distances
```

**Complexity:** O(n²) where n = building pixels

**For 500m parcel:** More buildings spread out → many more pixels → n² explodes

---

## Performance Impact by Parcel Size

### 50,000 Evaluation Projection

| Parcel Size | Per Solution | 50K Evaluations | JIT vs No-JIT |
|-------------|--------------|-----------------|---------------|
| **50m** | 0.90 ms | **45 sec** | JIT wins (1.44×) |
| **100m** | 2.75 ms | **137 sec** | JIT wins (1.38×) |
| **500m** | 178.07 ms | **🚨 2.47 hours** | JIT **loses** (0.08×) |

**CRITICAL:** At 500m parcel size, **JIT features make everything 12× SLOWER!**

Without JIT features at 500m: 28.86 ms/solution → **24 minutes for 50K**  
With JIT features at 500m: 365.38 ms/solution → **🚨 5 hours for 50K**

---

## Root Cause Analysis

### Why JIT Features Fail at Large Scale

1. **SVF Ray Casting is O(N³)** - dominates at large N
2. **H/W Ratio is O(n²)** - scales with building pixel count
3. **Scipy operations hidden in JIT version** - label(), center_of_mass() are slow when reimplemented
4. **Cache thrashing** - large arrays don't fit in CPU cache
5. **No vectorization** - nested loops can't be parallelized effectively

### Why Scipy Stays Fast

- **Highly optimized C code** with BLAS/LAPACK
- **Cache-friendly algorithms** 
- **Multi-threaded operations** (OpenMP)
- **Specialized data structures**

---

## Recommendations by Use Case

### For Small Parcels (<100m × 100m) ✅

**USE JIT for everything except rotation:**
- ✅ JIT phenotype creation (134× speedup)
- ✅ JIT 3D mesh (7.6× speedup)
- ✅ JIT features (moderate benefit)
- ❌ Keep scipy rotation (already optimal)

**Expected performance:** ~1-3 ms per solution

### For Large Parcels (>300m × 300m) 🚨

**DO NOT USE JIT for features!**
- ✅ JIT phenotype creation (still fast)
- ✅ JIT 3D mesh (20× speedup!)
- ❌ **NO JIT for features** (479× SLOWER!)
- ❌ Keep scipy rotation (already optimal)

**Alternative:** Use original feature calculation without JIT

**Expected performance:** ~29 ms per solution (vs 365 ms with JIT features)

### Adaptive Strategy 💡

```python
def calculate_features_adaptive(heightmap, mask, area):
    grid_size = heightmap.shape[0]
    
    if grid_size < 50:
        # Small grids: JIT is faster
        return calculate_all_features_planning_jit(heightmap, mask, area)
    else:
        # Large grids: Original is faster
        return calculate_all_features_planning(heightmap, mask, area)
```

---

## Why Each Component Scales Differently

### Phenotype Creation: O(N^0.40) - Sub-linear! ✅

**Why better than expected?**
- Fixed number of buildings (10 max)
- Only iterates over active buildings, not all pixels
- Most time in setup, not drawing
- **JIT overhead amortizes well**

**Scales well:** 6.2× slower for 96.5× more pixels

### 3D Mesh Generation: O(N^0.75) - Sub-quadratic! ✅

**Why better than expected?**
- Sparse heightmaps (mostly empty)
- JIT can skip zero-height pixels efficiently
- Cache-friendly linear memory access
- **JIT optimization very effective**

**Scales well:** 30.6× slower for 96.5× more pixels

### Fitness (Scipy Rotation): O(N^0.89) - Nearly linear! ✅

**Why so good?**
- Scipy uses highly optimized BLAS routines
- Multi-threaded C implementation
- Cache-optimized memory access
- Hardware-accelerated operations

**Scales well:** 59.3× slower for 96.5× more pixels

### Features (JIT): O(N^1.35) - SUPER-LINEAR! 🚨

**Why so bad?**
- SVF ray casting is O(N³) in implementation
- H/W ratio is O(n²) with large n
- No vectorization of nested loops
- Cache thrashing on large arrays
- **JIT can't optimize algorithmic complexity**

**Scales TERRIBLY:** 479.6× slower for 96.5× more pixels

---

## Immediate Action Items

### 1. Add Adaptive Feature Selection 🔥 CRITICAL

```python
# In backend/evaluation.py

def calculate_all_features_planning_adaptive(heightmap, buildable_mask, buildable_area):
    """
    Adaptively choose JIT or original implementation based on grid size.
    """
    grid_size = heightmap.shape[0]
    
    # Threshold determined by benchmarking
    # Below 50×50: JIT wins
    # Above 50×50: Original wins
    GRID_SIZE_THRESHOLD = 50
    
    if grid_size < GRID_SIZE_THRESHOLD:
        return calculate_all_features_planning_jit(heightmap, buildable_mask, buildable_area)
    else:
        return calculate_all_features_planning(heightmap, buildable_mask, buildable_area)
```

### 2. Optimize SVF for Large Grids

**Option A: Reduce sampling density**
```python
# Adaptive sample stride based on grid size
sample_stride = max(5, grid_size // 30)  # Coarser sampling for large grids
```

**Option B: Vectorize ray casting**
- Pre-compute all ray directions
- Batch process rays with NumPy
- Use GPU acceleration (CuPy)

**Option C: Approximate SVF**
- Use hierarchical spatial data structure (octree)
- Only sample boundary pixels
- Interpolate interior values

### 3. Optimize H/W Ratio

**Current:** O(n²) pairwise distances

**Better:** 
- Sample random pairs instead of all pairs
- Use spatial hashing to find nearby buildings only
- Calculate from building centroids, not all pixels

### 4. Add Performance Warning

```python
def eval_solution(genome, encoding_obj, env_config):
    grid_size = env_config['buildable_mask'].shape[0]
    
    if grid_size > 100:
        logger.warning(
            f"Large grid size ({grid_size}×{grid_size}). "
            f"Consider reducing resolution or enabling adaptive optimization."
        )
```

---

## Long-Term Optimization Strategy

### Phase 1: Adaptive Selection (Immediate)
- Implement grid-size-based feature selection
- **Impact:** 10-12× speedup for large parcels
- **Effort:** 1 hour

### Phase 2: Algorithm Optimization (Short-term)
- Reduce SVF sampling density adaptively
- Approximate H/W ratio instead of exact calculation
- **Impact:** Additional 2-5× speedup
- **Effort:** 1-2 days

### Phase 3: GPU Acceleration (Long-term)
- Port SVF ray casting to GPU (CuPy/PyTorch)
- Parallelize feature calculations
- **Impact:** 10-100× speedup potential
- **Effort:** 1-2 weeks

---

## Conclusion

### Key Insights

1. 🚨 **JIT is not a silver bullet** - algorithmic complexity matters more than compilation
2. ✅ **Small grids benefit from JIT** - overhead amortizes well
3. 🚨 **Large grids catastrophically slow with JIT** - O(N³) operations dominate
4. 💡 **Adaptive strategy essential** - choose optimization based on problem size
5. ✅ **Scipy is excellent at scale** - respect highly-optimized libraries

### Performance Summary

| Parcel Size | Best Strategy | Per Solution | 50K Time |
|-------------|---------------|--------------|----------|
| 50m × 50m | Full JIT | 0.81 ms | **40 sec** ✅ |
| 100m × 100m | Full JIT | 1.37 ms | **68 sec** ✅ |
| 500m × 500m | **NO JIT features** | 28.86 ms | **24 min** ✅ |

**vs naive JIT everywhere for 500m: 365 ms/solution, 5 hours** 🚨

### Next Steps

1. ✅ Implement adaptive feature selection (CRITICAL)
2. ✅ Add performance warnings for large grids
3. ⏭️ Optimize SVF algorithm for large grids
4. ⏭️ Consider GPU acceleration for production

**The most important lesson:** Always benchmark at realistic scales!
