"""
Performance Comparison: Original vs Planning Feature Sets

This script benchmarks the computation time of both feature sets to identify
performance bottlenecks.
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.evaluation import (
    calculate_all_features,
    calculate_all_features_planning,
    calculate_sky_view_factor
)

def create_test_scenarios():
    """Create representative test scenarios."""
    scenarios = []
    
    # Scenario 1: Simple - single building
    heightmap1 = np.zeros((30, 30))
    heightmap1[12:18, 12:18] = 15.0
    mask1 = np.ones((30, 30), dtype=bool)
    scenarios.append(("Simple (1 building)", heightmap1, mask1, 8100.0))
    
    # Scenario 2: Moderate - 3 buildings
    heightmap2 = np.zeros((30, 30))
    heightmap2[5:11, 5:11] = 12.0
    heightmap2[5:11, 19:25] = 18.0
    heightmap2[19:25, 12:18] = 15.0
    mask2 = np.ones((30, 30), dtype=bool)
    scenarios.append(("Moderate (3 buildings)", heightmap2, mask2, 8100.0))
    
    # Scenario 3: Complex - 6 buildings with varying heights
    heightmap3 = np.zeros((30, 30))
    heightmap3[3:9, 3:9] = 10.0
    heightmap3[3:9, 12:18] = 15.0
    heightmap3[3:9, 21:27] = 20.0
    heightmap3[15:21, 3:9] = 12.0
    heightmap3[15:21, 12:18] = 18.0
    heightmap3[15:21, 21:27] = 14.0
    mask3 = np.ones((30, 30), dtype=bool)
    scenarios.append(("Complex (6 buildings)", heightmap3, mask3, 8100.0))
    
    # Scenario 4: Dense - street canyon pattern
    heightmap4 = np.zeros((30, 30))
    heightmap4[2:28, 2:7] = 18.0
    heightmap4[2:28, 23:28] = 18.0
    heightmap4[2:7, 7:23] = 15.0
    heightmap4[23:28, 7:23] = 15.0
    mask4 = np.ones((30, 30), dtype=bool)
    scenarios.append(("Dense (street canyon)", heightmap4, mask4, 8100.0))
    
    # Scenario 5: Large grid (typical optimization size)
    heightmap5 = np.zeros((40, 40))
    for i in range(4):
        for j in range(4):
            r = 3 + i * 9
            c = 3 + j * 9
            h = 10 + np.random.uniform(0, 15)
            heightmap5[r:r+6, c:c+6] = h
    mask5 = np.ones((40, 40), dtype=bool)
    scenarios.append(("Large grid (40×40, 16 buildings)", heightmap5, mask5, 14400.0))
    
    return scenarios


def benchmark_feature_set(name, feature_func, heightmap, mask, area, num_iterations=100):
    """Benchmark a feature calculation function."""
    times = []
    
    # Warm-up run
    _ = feature_func(heightmap, mask, area)
    
    # Timed runs
    for _ in range(num_iterations):
        start = time.perf_counter()
        result = feature_func(heightmap, mask, area)
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to ms
    
    times = np.array(times)
    return {
        'mean': np.mean(times),
        'std': np.std(times),
        'min': np.min(times),
        'max': np.max(times),
        'median': np.median(times),
        'result': result
    }


def benchmark_svf_only(heightmap, num_iterations=50):
    """Benchmark SVF calculation separately."""
    pixel_size = 3.0  # Standard pixel size
    times = []
    
    # Warm-up
    _ = calculate_sky_view_factor(heightmap, pixel_size)
    
    # Timed runs
    for _ in range(num_iterations):
        start = time.perf_counter()
        result = calculate_sky_view_factor(heightmap, pixel_size)
        end = time.perf_counter()
        times.append((end - start) * 1000)
    
    times = np.array(times)
    return {
        'mean': np.mean(times),
        'std': np.std(times),
        'min': np.min(times),
        'max': np.max(times),
        'median': np.median(times),
        'result': result
    }


def main():
    print("=" * 80)
    print("FEATURE SET PERFORMANCE COMPARISON")
    print("=" * 80)
    print("\nComparing computation time between:")
    print("  1. Original features (8 features)")
    print("  2. Planning features (8 features including SVF)")
    print("\nIterations: 100 per scenario")
    print("=" * 80)
    
    scenarios = create_test_scenarios()
    
    all_results = []
    
    for scenario_name, heightmap, mask, area in scenarios:
        print(f"\n{'=' * 80}")
        print(f"SCENARIO: {scenario_name}")
        print(f"Grid size: {heightmap.shape}")
        print(f"Occupied pixels: {np.sum(heightmap > 0)}")
        print(f"{'=' * 80}")
        
        # Benchmark original features
        print("\n[1] Benchmarking ORIGINAL features...")
        original_stats = benchmark_feature_set(
            "Original",
            calculate_all_features,
            heightmap, mask, area
        )
        
        # Benchmark planning features
        print("[2] Benchmarking PLANNING features...")
        planning_stats = benchmark_feature_set(
            "Planning",
            calculate_all_features_planning,
            heightmap, mask, area
        )
        
        # Benchmark SVF separately
        print("[3] Benchmarking SVF only...")
        svf_stats = benchmark_svf_only(heightmap, num_iterations=50)
        
        # Calculate overhead
        overhead_ms = planning_stats['mean'] - original_stats['mean']
        overhead_pct = (overhead_ms / original_stats['mean']) * 100
        svf_contribution_pct = (svf_stats['mean'] / planning_stats['mean']) * 100
        
        # Display results
        print("\n" + "-" * 80)
        print("RESULTS:")
        print("-" * 80)
        print(f"{'Metric':<25} {'Original':<15} {'Planning':<15} {'SVF Only':<15}")
        print("-" * 80)
        print(f"{'Mean time (ms)':<25} {original_stats['mean']:>14.3f} {planning_stats['mean']:>14.3f} {svf_stats['mean']:>14.3f}")
        print(f"{'Median time (ms)':<25} {original_stats['median']:>14.3f} {planning_stats['median']:>14.3f} {svf_stats['median']:>14.3f}")
        print(f"{'Std dev (ms)':<25} {original_stats['std']:>14.3f} {planning_stats['std']:>14.3f} {svf_stats['std']:>14.3f}")
        print(f"{'Min time (ms)':<25} {original_stats['min']:>14.3f} {planning_stats['min']:>14.3f} {svf_stats['min']:>14.3f}")
        print(f"{'Max time (ms)':<25} {original_stats['max']:>14.3f} {planning_stats['max']:>14.3f} {svf_stats['max']:>14.3f}")
        print("-" * 80)
        print(f"\nPlanning overhead: +{overhead_ms:.3f} ms ({overhead_pct:.1f}% slower)")
        print(f"SVF contribution: {svf_contribution_pct:.1f}% of planning time")
        print(f"Other features overhead: {planning_stats['mean'] - svf_stats['mean']:.3f} ms")
        
        all_results.append({
            'scenario': scenario_name,
            'grid_shape': heightmap.shape,
            'original_mean': original_stats['mean'],
            'planning_mean': planning_stats['mean'],
            'svf_mean': svf_stats['mean'],
            'overhead_ms': overhead_ms,
            'overhead_pct': overhead_pct,
            'svf_contribution_pct': svf_contribution_pct
        })
    
    # Summary across all scenarios
    print("\n" + "=" * 80)
    print("SUMMARY ACROSS ALL SCENARIOS")
    print("=" * 80)
    print(f"\n{'Scenario':<35} {'Original':<12} {'Planning':<12} {'Overhead':<12}")
    print("-" * 80)
    for res in all_results:
        overhead_str = f"+{res['overhead_ms']:.1f}ms ({res['overhead_pct']:.0f}%)"
        print(f"{res['scenario']:<35} {res['original_mean']:>10.2f}ms {res['planning_mean']:>10.2f}ms {overhead_str:>12}")
    
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    
    avg_overhead_pct = np.mean([r['overhead_pct'] for r in all_results])
    avg_svf_contribution = np.mean([r['svf_contribution_pct'] for r in all_results])
    
    print(f"\nAverage overhead: {avg_overhead_pct:.1f}%")
    print(f"Average SVF contribution to planning time: {avg_svf_contribution:.1f}%")
    
    print("\n" + "-" * 80)
    print("BOTTLENECK IDENTIFICATION:")
    print("-" * 80)
    
    # Identify primary bottleneck
    if avg_svf_contribution > 70:
        print("\n⚠ PRIMARY BOTTLENECK: Sky View Factor (SVF) calculation")
        print(f"   SVF accounts for ~{avg_svf_contribution:.0f}% of planning feature time")
        print("\n   Potential optimizations:")
        print("   1. Reduce num_rays (currently 16, try 12 or 8)")
        print("   2. Increase sample_stride (currently 5, try 6 or 7)")
        print("   3. Implement Numba JIT compilation (5-10× speedup)")
        print("   4. Cache ray directions globally")
        print("   5. For QD optimization: Pre-compute SVF less frequently")
    elif avg_overhead_pct > 50:
        print("\n⚠ MODERATE OVERHEAD: Multiple factors")
        print(f"   SVF: ~{avg_svf_contribution:.0f}% of planning time")
        other_pct = 100 - avg_svf_contribution
        print(f"   Other features: ~{other_pct:.0f}% of planning time")
        print("\n   Review all planning feature calculations for optimization opportunities")
    else:
        print("\n✓ ACCEPTABLE OVERHEAD: Planning features are reasonably efficient")
        print(f"   Average slowdown: {avg_overhead_pct:.1f}%")
    
    # Optimization impact estimation
    print("\n" + "-" * 80)
    print("OPTIMIZATION IMPACT:")
    print("-" * 80)
    
    typical_case = all_results[2]  # Complex scenario
    evaluations_per_gen = 100  # Typical QD optimization
    generations = 500
    total_evaluations = evaluations_per_gen * generations
    
    original_total_time = (typical_case['original_mean'] / 1000) * total_evaluations
    planning_total_time = (typical_case['planning_mean'] / 1000) * total_evaluations
    overhead_total_time = planning_total_time - original_total_time
    
    print(f"\nFor a typical optimization run:")
    print(f"  - {evaluations_per_gen} evaluations/generation × {generations} generations = {total_evaluations:,} evaluations")
    print(f"  - Original features: {original_total_time:.1f}s ({original_total_time/60:.1f} min)")
    print(f"  - Planning features: {planning_total_time:.1f}s ({planning_total_time/60:.1f} min)")
    print(f"  - Added time: {overhead_total_time:.1f}s ({overhead_total_time/60:.1f} min)")
    
    # Optimization scenarios
    print("\n" + "-" * 80)
    print("OPTIMIZATION SCENARIOS:")
    print("-" * 80)
    
    # Scenario 1: Reduce rays
    svf_time = typical_case['svf_mean']
    reduced_rays_speedup = 0.7  # 8 rays instead of 16 → ~30% faster
    new_svf_time = svf_time * reduced_rays_speedup
    new_planning_time = typical_case['planning_mean'] - svf_time + new_svf_time
    new_total_time = (new_planning_time / 1000) * total_evaluations
    time_saved = planning_total_time - new_total_time
    
    print(f"\n1. Reduce SVF rays (16→8):")
    print(f"   New planning time: {new_planning_time:.2f}ms (vs {typical_case['planning_mean']:.2f}ms)")
    print(f"   Time saved per optimization: {time_saved:.1f}s ({time_saved/60:.1f} min)")
    
    # Scenario 2: Increase stride
    stride_speedup = 0.6  # stride 5→7 → ~40% faster
    new_svf_time2 = svf_time * stride_speedup
    new_planning_time2 = typical_case['planning_mean'] - svf_time + new_svf_time2
    new_total_time2 = (new_planning_time2 / 1000) * total_evaluations
    time_saved2 = planning_total_time - new_total_time2
    
    print(f"\n2. Increase SVF stride (5→7):")
    print(f"   New planning time: {new_planning_time2:.2f}ms (vs {typical_case['planning_mean']:.2f}ms)")
    print(f"   Time saved per optimization: {time_saved2:.1f}s ({time_saved2/60:.1f} min)")
    
    # Scenario 3: Numba JIT
    numba_speedup = 0.15  # ~85% faster
    new_svf_time3 = svf_time * numba_speedup
    new_planning_time3 = typical_case['planning_mean'] - svf_time + new_svf_time3
    new_total_time3 = (new_planning_time3 / 1000) * total_evaluations
    time_saved3 = planning_total_time - new_total_time3
    
    print(f"\n3. Implement Numba JIT compilation:")
    print(f"   New planning time: {new_planning_time3:.2f}ms (vs {typical_case['planning_mean']:.2f}ms)")
    print(f"   Time saved per optimization: {time_saved3:.1f}s ({time_saved3/60:.1f} min)")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if avg_overhead_pct > 100:
        print("\n⚠ HIGH PRIORITY: Optimization needed")
        print("  Planning features are >2× slower than original")
        print("  Recommended actions:")
        print("  1. Implement Numba JIT for SVF (biggest impact)")
        print("  2. Reduce num_rays to 8 (quick win)")
        print("  3. Consider computing SVF every N generations instead of every evaluation")
    elif avg_overhead_pct > 50:
        print("\n⚡ MEDIUM PRIORITY: Consider optimization")
        print("  Planning features are notably slower but acceptable")
        print("  Recommended actions:")
        print("  1. Try reducing num_rays to 12 (balance accuracy vs speed)")
        print("  2. Profile other planning features (GRZ, GFZ, H/W ratio)")
    else:
        print("\n✓ LOW PRIORITY: Current performance acceptable")
        print("  Overhead is minimal, optimization not urgent")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error during benchmarking: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
