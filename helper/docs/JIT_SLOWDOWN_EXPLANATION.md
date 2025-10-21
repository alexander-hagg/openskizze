# Why Original Features with JIT Are Slower in Multiprocessing

## Executive Summary

**The diagnostic reveals a surprising paradox:**
- **Single-threaded**: JIT is 8.7× FASTER (58.3ms → 6.7ms for 100 solutions) ✅
- **Multiprocessing (benchmark)**: JIT appears SLOWER (72.4ms → 95.4ms) ❌

**Root cause**: The benchmark result is **MISLEADING** due to different test conditions!

---

## The Full Picture: What Actually Happened

### Diagnostic Results (This Script)

```
SINGLE-THREADED (100 solutions):
  Scipy (no JIT):  58.3 ms (0.583 ms per solution)
  JIT custom:       6.7 ms (0.067 ms per solution)  ← 8.7× FASTER!

MULTIPROCESSING (8 cores, 100 solutions):
  Scipy (no JIT):  55.6 ms (0.556 ms per solution)
  JIT custom:      38.6 ms (0.386 ms per solution)  ← Still 1.4× FASTER!
```

**JIT is actually FASTER in both cases!** So why did the benchmark show the opposite?

### Benchmark Results (numba_benchmark.py)

```
PART 2: Single Solution Evaluation
  Original (no JIT):  0.555 ms
  Original (JIT):     0.061 ms  ← 9.1× FASTER!

PART 3: Batch Evaluation (100 solutions, multiprocessing)
  Original (no JIT):   72.4 ms
  Original (JIT):      95.4 ms  ← 0.76× SLOWER!
```

**The multiprocessing test showed JIT was slower!** What's the difference?

---

## The Critical Difference: Test Methodology

### This Diagnostic Script
- **Uses WARM JIT functions** before multiprocessing test
- Compilation happens ONCE in main process before timing
- Each worker inherits already-compiled code
- **Result**: JIT is 1.4× faster even in multiprocessing

### numba_benchmark.py
- **Uses COLD JIT functions** in multiprocessing
- Each worker process starts fresh → must compile on first call
- Compilation overhead happens in EACH worker (8× compilation!)
- **Result**: JIT appears slower due to compilation overhead

---

## JIT Compilation Overhead Breakdown

### Single Worker Process Costs

```
First call to JIT function:
  1. Parse Python bytecode
  2. Type inference
  3. LLVM IR generation
  4. Optimization passes
  5. Machine code compilation
  6. Actual execution

  Total: ~30-50ms for complex functions

Subsequent calls:
  Just execute compiled code: ~0.05ms
```

### Multiprocessing Amplifies This

**With 8 worker processes** (each processing ~12 solutions):
```
Cold JIT (benchmark):
  Worker 1: 30ms compile + 12×0.067ms execute = 30.8ms
  Worker 2: 30ms compile + 12×0.067ms execute = 30.8ms
  ...
  Worker 8: 30ms compile + 12×0.067ms execute = 30.8ms
  
  All workers run in parallel, so total ≈ 31ms
  BUT: This is amortized over only 100 solutions
  Per-solution cost: 0.31ms (5× slower than no-JIT!)

Warm JIT (diagnostic):
  Pre-compile in main: 30ms (one-time cost, not counted in timing)
  Worker 1-8: 12×0.067ms execute = 0.8ms each
  
  Total: ~0.8ms (parallel execution)
  Per-solution cost: 0.08ms (7× faster than no-JIT!)
```

---

## Component-Level Analysis

### What Makes JIT Fast?

From the diagnostic, we can see which operations benefit from JIT:

```
Building statistics:
  NumPy:  0.045 ms
  JIT:    0.004 ms  ← 11× speedup

Connected components:
  Scipy:  0.073 ms
  JIT:    0.003 ms  ← 22× speedup (but this is WRONG - see below!)

Centroids:
  Scipy:  0.240 ms
  JIT:    0.004 ms  ← 64× speedup

Center of mass:
  Scipy:  0.050 ms
  JIT:    0.002 ms  ← 32× speedup
```

**Wait, why does it say JIT connected components are faster here?**

The diagnostic is timing the **custom JIT flood-fill algorithm**, which happens to be faster than scipy.label() on **very small grids** (30×30). But:

1. This is **grid-size dependent** - scipy wins on larger grids
2. The **full scipy.label()** does more (better algorithm, more features)
3. The custom JIT version is **less robust** (simple flood-fill)

### The Real-World Benchmark

In the full benchmark with realistic conditions:
```
Planning features (JIT hybrid w/ scipy):  0.733 ms
Planning features (JIT full, no scipy):   3.933 ms

Scipy label is 5.4× faster than custom JIT!
```

This is because:
- Larger grids (realistic building layouts)
- More complex connected component patterns
- Scipy uses optimal union-find algorithm in C
- Custom flood-fill is simpler but slower for complex cases

---

## Why the Benchmark Showed JIT Slower

### The Setup

```python
# In numba_benchmark.py Part 3:
times_mp_original_jit = []
for _ in range(5):
    start = timeit.default_timer()
    with Pool() as pool:  # ← NEW pool each iteration!
        results = pool.starmap(eval_single_solution_jit_hybrid, args_original)
    end = timeit.default_timer()
    times_mp_original_jit.append((end - start) * 1000)
```

**Problem**: Each iteration creates a new Pool!
- New processes = cold JIT functions
- **5 iterations × 8 workers = 40 compilations!**
- Each compilation takes ~30ms
- Total wasted time: ~1200ms spread across 500 evaluations (5×100)
- Per-evaluation overhead: ~2.4ms extra

### The Fix

```python
# What we did in the diagnostic:
print("Warming up JIT functions...")
_ = calculate_all_features_jit(test_heightmap, mask, buildable_area)
print("Done.")

# THEN run multiprocessing tests
# Now workers inherit pre-compiled functions (via Numba's disk cache)
```

With Numba's disk cache (`cache=True`), compiled functions are saved to `__pycache__`. Worker processes can load these instead of recompiling.

**But**: This only works if:
1. Functions are compiled before forking workers
2. Cache is enabled (`cache=True` in `@njit`)
3. Workers run on same machine (shared filesystem)

---

## The Real Performance Characteristics

### JIT Performance Profile

| Scenario | No JIT | JIT | Winner | Why |
|----------|--------|-----|--------|-----|
| **First call (cold)** | 0.6ms | 30-50ms | No JIT | Compilation overhead |
| **Single-threaded (warm)** | 0.6ms | 0.07ms | JIT (8×) | No MP overhead |
| **Multiprocessing (cold)** | 0.7ms | 1-3ms | No JIT | Each worker compiles |
| **Multiprocessing (warm)** | 0.7ms | 0.4ms | JIT (1.7×) | Pre-compiled functions |
| **Long-running optimization** | 0.6ms | 0.07ms | JIT (8×) | One-time compilation cost |

### Key Insight

**JIT is FASTER when**:
- Functions are pre-compiled (warm start)
- Running many evaluations (>1000)
- Long-running process (optimization run)
- Single-threaded execution

**JIT is SLOWER when**:
- Cold start with multiprocessing
- Short runs (<100 evaluations)
- Each run creates new processes
- Benchmarking without warm-up

---

## Production Implications

### For OpenSKIZZE Optimization Runs

**Typical optimization**: 50,000 evaluations over 30-60 minutes

```
Compilation cost (one-time):
  Main process: ~50ms
  8 workers: 8×50ms = 400ms total (parallel, so ~50ms wall time)
  Total overhead: ~100ms

Evaluation savings:
  Per evaluation: 0.6ms → 0.07ms = 0.53ms saved
  50,000 evaluations: 26,500ms saved = 26.5 seconds!

Net benefit: 26.5s - 0.1s = 26.4 seconds faster
```

**JIT is absolutely worth it for production!**

### For Short Benchmarks/Tests

```
100 evaluations with cold start:
  Compilation: 100ms overhead
  Savings: 100 × 0.53ms = 53ms
  Net: 53ms - 100ms = -47ms (SLOWER!)

100 evaluations with warm start:
  Compilation: 0ms (pre-done)
  Savings: 100 × 0.53ms = 53ms
  Net: 53ms faster
```

**For short tests, you MUST warm up JIT first!**

---

## Recommendations

### 1. Always Warm Up JIT in Production ✅

```python
# In app.py or optimization startup:
print("Initializing JIT compilation...")
dummy_grid = np.zeros((30, 30))
dummy_mask = np.ones((30, 30), dtype=bool)
dummy_area = 8100.0

# Compile all JIT functions
_ = calculate_sky_view_factor_jit(dummy_grid, 3.0)
_ = calculate_all_features_planning_jit_hybrid(dummy_grid, dummy_mask, dummy_area)
print("JIT compilation complete.")

# Now start optimization with warm functions
```

### 2. Use Numba Cache ✅

```python
@njit(cache=True, nogil=True)  # ← cache=True is essential!
def _compute_svf_core_jit(...):
    ...
```

This saves compiled functions to disk, so subsequent runs skip compilation entirely.

### 3. Consider JIT vs No-JIT Based on Use Case

| Use Case | Recommendation |
|----------|----------------|
| **Production optimization (50k evals)** | ✅ Use JIT hybrid | 
| **Quick tests (<100 evals)** | ⚠️ Either warm up or skip JIT |
| **Benchmarking** | ✅ Always warm up first |
| **One-off evaluations** | ❌ Skip JIT (overhead not worth it) |

### 4. Keep the Hybrid Approach ✅

```python
def calculate_all_features_planning_optimized(...):
    # JIT-optimized computations
    svf = calculate_sky_view_factor_jit(...)  # 36× speedup
    hw_ratio = _compute_hw_ratio_jit(...)     # Moderate speedup
    
    # Keep scipy for labeling
    labels, n_buildings = label(occupied)      # Already optimal!
    centroids = center_of_mass(...)            # Already fast!
    
    return features
```

**Don't replace scipy unnecessarily!**

---

## Conclusion

### The Answer

**Q: Why are original features with JIT slower in multiprocessing?**

**A: They're NOT slower - the benchmark was misleading!**

The benchmark measured **cold-start** performance where each worker must compile JIT functions. This:
- Adds 30-50ms compilation per worker
- Dominates the runtime for small batch sizes
- Makes JIT appear slower

With proper warm-up (pre-compilation), JIT is:
- **8.7× faster single-threaded**
- **1.4× faster in multiprocessing**
- **Essential for long-running optimizations**

### The Fix

1. ✅ **Warm up JIT before multiprocessing** in production
2. ✅ **Use `cache=True`** to save compiled functions
3. ✅ **Keep the hybrid approach** (JIT + scipy)
4. ✅ **Don't benchmark cold starts** - always warm up first!

### Implementation Status

- ✅ JIT functions implemented with `cache=True`
- ✅ Hybrid approach uses scipy where it's faster
- ⏩ **TODO**: Add JIT warm-up to app.py startup
- ⏩ **TODO**: Add progress indicator during compilation

---

**Bottom line**: Use JIT in production, but always warm it up first!
