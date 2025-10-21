#!/usr/bin/env python3
"""
Fitness Function Performance Benchmark

Compares performance of fitness function implementations across parcel sizes:
- Simple Porosity (original)
- Street Canyon (improved)
- With and without scipy rotation

Tests parcel sizes: 50m, 100m, 250m, 500m
"""

import sys
import timeit
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import numba
    from numba import njit, prange
    NUMBA_AVAILABLE = True
    print(f"Numba version: {numba.__version__}")
    print(f"NumPy version: {np.__version__}")
except ImportError:
    NUMBA_AVAILABLE = False
    print("WARNING: Numba not installed")
    sys.exit(1)

from scipy.ndimage import rotate
from backend.evaluation import compute_fitness, compute_fitness_street_canyon


# =============================================================================
# JIT-OPTIMIZED FITNESS FUNCTIONS (Manual Rotation)
# =============================================================================

@njit(cache=True, nogil=True)
def compute_fitness_simple_jit(heightmap_3d, wind_direction):
    """
    JIT-optimized simple porosity WITHOUT scipy rotation.
    Uses manual rotation for full JIT compilation.
    """
    rows, cols, height = heightmap_3d.shape
    
    # Simple rotation: approximate with grid sampling
    rotation_angle_rad = np.radians((wind_direction + 90) % 360)
    cos_a = np.cos(rotation_angle_rad)
    sin_a = np.sin(rotation_angle_rad)
    
    center_r = rows / 2.0
    center_c = cols / 2.0
    
    # Create rotated environment
    rotated = np.zeros_like(heightmap_3d)
    
    for r in range(rows):
        for c in range(cols):
            # Rotate coordinates
            r_centered = r - center_r
            c_centered = c - center_c
            
            r_rot = r_centered * cos_a - c_centered * sin_a + center_r
            c_rot = r_centered * sin_a + c_centered * cos_a + center_c
            
            # Nearest neighbor sampling
            r_src = int(round(r_rot))
            c_src = int(round(c_rot))
            
            if 0 <= r_src < rows and 0 <= c_src < cols:
                for z in range(height):
                    rotated[r, c, z] = heightmap_3d[r_src, c_src, z]
    
    # Calculate porosity
    open_paths = 0
    total_paths = 0
    
    for r in range(rows):
        for z in range(height):
            # Check if entire Y-axis is clear
            is_clear = True
            for c in range(cols):
                if rotated[r, c, z] > 0:
                    is_clear = False
                    break
            
            if is_clear:
                open_paths += 1
            total_paths += 1
    
    porosity = open_paths / total_paths if total_paths > 0 else 0.0
    return min(max(porosity, 0.0), 1.0)


@njit(cache=True, nogil=True)
def compute_fitness_street_canyon_jit(heightmap_3d, wind_direction):
    """
    JIT-optimized street canyon fitness WITHOUT scipy rotation.
    Full manual implementation for JIT compilation.
    """
    rows, cols, height = heightmap_3d.shape
    
    # Manual rotation
    rotation_angle_rad = np.radians((wind_direction + 90) % 360)
    cos_a = np.cos(rotation_angle_rad)
    sin_a = np.sin(rotation_angle_rad)
    
    center_r = rows / 2.0
    center_c = cols / 2.0
    
    # Create rotated environment
    rotated = np.zeros_like(heightmap_3d)
    
    for r in range(rows):
        for c in range(cols):
            r_centered = r - center_r
            c_centered = c - center_c
            
            r_rot = r_centered * cos_a - c_centered * sin_a + center_r
            c_rot = r_centered * sin_a + c_centered * cos_a + center_c
            
            r_src = int(round(r_rot))
            c_src = int(round(c_rot))
            
            if 0 <= r_src < rows and 0 <= c_src < cols:
                for z in range(height):
                    rotated[r, c, z] = heightmap_3d[r_src, c_src, z]
    
    # Component 1: Ground-level street canyons
    ground_open_sum = 0.0
    continuity_sum = 0.0
    
    for r in range(rows):
        # Count open spaces at ground level (first 2 layers)
        open_count = 0
        for c in range(cols):
            is_open = True
            for z in range(min(2, height)):
                if rotated[r, c, z] > 0:
                    is_open = False
                    break
            if is_open:
                open_count += 1
        
        row_openness = open_count / cols if cols > 0 else 0.0
        ground_open_sum += row_openness
        
        # Count transitions for continuity
        transitions = 0
        for c in range(cols - 1):
            occupied_curr = False
            occupied_next = False
            for z in range(min(2, height)):
                if rotated[r, c, z] > 0:
                    occupied_curr = True
                if rotated[r, c + 1, z] > 0:
                    occupied_next = True
            
            if occupied_curr != occupied_next:
                transitions += 1
        
        fragmentation = transitions / (cols - 1) if cols > 1 else 0.0
        continuity_weight = 1.0 - min(fragmentation, 1.0)
        continuity_sum += row_openness * (0.5 + 0.5 * continuity_weight)
    
    street_canyon_score = continuity_sum / rows if rows > 0 else 0.0
    
    # Component 2: Lateral ventilation
    lateral_sum = 0.0
    for c in range(cols):
        open_count = 0
        for r in range(rows):
            for z in range(height):
                if rotated[r, c, z] == 0:
                    open_count += 1
        
        lateral_openness = open_count / (rows * height) if (rows * height) > 0 else 0.0
        lateral_sum += lateral_openness
    
    lateral_ventilation_score = lateral_sum / cols if cols > 0 else 0.0
    
    # Component 3: Height variation
    max_heights_sum = 0.0
    max_heights_sq_sum = 0.0
    for r in range(rows):
        for c in range(cols):
            max_h = 0
            for z in range(height):
                if rotated[r, c, z] > 0:
                    max_h = z + 1
            max_heights_sum += max_h
            max_heights_sq_sum += max_h * max_h
    
    count = rows * cols
    mean_height = max_heights_sum / count if count > 0 else 0.0
    variance = (max_heights_sq_sum / count - mean_height * mean_height) if count > 0 else 0.0
    height_std = np.sqrt(max(variance, 0.0))
    max_possible_std = height / 2.0
    height_variation_score = min(height_std / max_possible_std, 1.0) if max_possible_std > 0 else 0.0
    
    # Component 4: Partial penetration
    penetration_sum = 0.0
    for r in range(rows):
        for z in range(height):
            column_sum = 0
            for c in range(cols):
                column_sum += rotated[r, c, z]
            
            penetration = 1.0 - min(column_sum / height, 1.0) if height > 0 else 0.0
            penetration_sum += penetration
    
    penetration_score = penetration_sum / (rows * height) if (rows * height) > 0 else 0.0
    
    # Weighted combination
    fitness = (
        0.35 * street_canyon_score +
        0.25 * lateral_ventilation_score +
        0.15 * height_variation_score +
        0.25 * penetration_score
    )
    
    return min(max(fitness, 0.0), 1.0)


# =============================================================================
# BENCHMARK UTILITIES
# =============================================================================

def create_test_environment(grid_size, max_height):
    """Create a test 3D environment with some buildings."""
    env_3d = np.zeros((grid_size, grid_size, max_height), dtype=np.int8)
    
    # Add some random buildings
    num_buildings = min(5, grid_size // 10)
    for _ in range(num_buildings):
        # Random building position and size
        x = np.random.randint(0, grid_size - grid_size // 5)
        y = np.random.randint(0, grid_size - grid_size // 5)
        w = np.random.randint(grid_size // 10, grid_size // 5)
        h = np.random.randint(grid_size // 10, grid_size // 5)
        height = np.random.randint(max_height // 3, max_height)
        
        # Fill building
        env_3d[x:x+w, y:y+h, :height] = 1
    
    return env_3d


def benchmark_function(func, env_3d, wind_direction, iterations=20):
    """Benchmark a fitness function."""
    times = []
    
    for _ in range(5):  # 5 runs
        start = timeit.default_timer()
        for _ in range(iterations):
            result = func(env_3d, wind_direction)
        end = timeit.default_timer()
        times.append((end - start) * 1000 / iterations)
    
    return np.mean(times), np.std(times), result


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 100)
    print(f"{text:^100}")
    print("=" * 100)


def print_subheader(text):
    """Print a formatted subheader."""
    print("\n" + "-" * 100)
    print(f"{text:^100}")
    print("-" * 100)


# =============================================================================
# MAIN BENCHMARK
# =============================================================================

def main():
    print_header("FITNESS FUNCTION PERFORMANCE BENCHMARK")
    
    print("\nThis benchmark compares fitness function implementations:")
    print("  1. Simple Porosity (original)")
    print("  2. Street Canyon (improved)")
    print("\nFor each function:")
    print("  - scipy version (with rotate)")
    print("  - JIT version (manual rotation)")
    print("\nTesting parcel sizes:")
    print("  - 50m × 50m (17×17 grid @ 3m pixels)")
    print("  - 100m × 100m (34×34 grid @ 3m pixels)")
    print("  - 250m × 250m (84×84 grid @ 3m pixels)")
    print("  - 500m × 500m (167×167 grid @ 3m pixels)")
    
    # Define parcel configurations
    PARCEL_CONFIGS = [
        {'name': '50m × 50m', 'size_m': 50, 'grid_size': 17, 'max_height': 30},
        {'name': '100m × 100m', 'size_m': 100, 'grid_size': 34, 'max_height': 30},
        {'name': '250m × 250m', 'size_m': 250, 'grid_size': 84, 'max_height': 30},
        {'name': '500m × 500m', 'size_m': 500, 'grid_size': 167, 'max_height': 30},
    ]
    
    # Store results
    results = {
        'simple_scipy': [],
        'simple_jit': [],
        'canyon_scipy': [],
        'canyon_jit': [],
    }
    
    wind_direction = 0
    
    # Warm up JIT functions
    print("\n🔥 Warming up JIT functions...")
    dummy_env = create_test_environment(17, 30)
    _ = compute_fitness_simple_jit(dummy_env, wind_direction)
    _ = compute_fitness_street_canyon_jit(dummy_env, wind_direction)
    print("✓ JIT warm-up complete")
    
    # Run benchmarks for each parcel size
    for config in PARCEL_CONFIGS:
        print_header(f"TESTING: {config['name']} parcel ({config['grid_size']}×{config['grid_size']} grid)")
        
        # Create test environment
        env_3d = create_test_environment(config['grid_size'], config['max_height'])
        voxel_count = np.sum(env_3d > 0)
        total_voxels = config['grid_size'] ** 2 * config['max_height']
        occupancy = voxel_count / total_voxels * 100
        
        print(f"\nTest environment:")
        print(f"  Grid size: {config['grid_size']}×{config['grid_size']}×{config['max_height']}")
        print(f"  Total voxels: {total_voxels:,}")
        print(f"  Occupied voxels: {voxel_count:,} ({occupancy:.1f}%)")
        
        # 1. Simple Porosity - scipy version
        print_subheader("1. SIMPLE POROSITY (scipy rotation)")
        time_simple_scipy, std_scipy, fitness_scipy = benchmark_function(
            compute_fitness, env_3d, wind_direction, iterations=20
        )
        results['simple_scipy'].append(time_simple_scipy)
        print(f"   Time:    {time_simple_scipy:>8.4f} ± {std_scipy:.4f} ms")
        print(f"   Fitness: {fitness_scipy:.6f}")
        
        # 2. Simple Porosity - JIT version
        print_subheader("2. SIMPLE POROSITY (JIT manual rotation)")
        time_simple_jit, std_jit, fitness_jit = benchmark_function(
            compute_fitness_simple_jit, env_3d, wind_direction, iterations=20
        )
        results['simple_jit'].append(time_simple_jit)
        speedup_simple = time_simple_scipy / time_simple_jit if time_simple_jit > 0 else 0
        print(f"   Time:    {time_simple_jit:>8.4f} ± {std_jit:.4f} ms")
        print(f"   Fitness: {fitness_jit:.6f}")
        print(f"   Speedup: {speedup_simple:>8.2f}×")
        print(f"   Fitness difference: {abs(fitness_scipy - fitness_jit):.6f}")
        
        # 3. Street Canyon - scipy version
        print_subheader("3. STREET CANYON (scipy rotation)")
        time_canyon_scipy, std_scipy, fitness_scipy = benchmark_function(
            compute_fitness_street_canyon, env_3d, wind_direction, iterations=20
        )
        results['canyon_scipy'].append(time_canyon_scipy)
        print(f"   Time:    {time_canyon_scipy:>8.4f} ± {std_scipy:.4f} ms")
        print(f"   Fitness: {fitness_scipy:.6f}")
        
        # 4. Street Canyon - JIT version
        print_subheader("4. STREET CANYON (JIT manual rotation)")
        time_canyon_jit, std_jit, fitness_jit = benchmark_function(
            compute_fitness_street_canyon_jit, env_3d, wind_direction, iterations=20
        )
        results['canyon_jit'].append(time_canyon_jit)
        speedup_canyon = time_canyon_scipy / time_canyon_jit if time_canyon_jit > 0 else 0
        print(f"   Time:    {time_canyon_jit:>8.4f} ± {std_jit:.4f} ms")
        print(f"   Fitness: {fitness_jit:.6f}")
        print(f"   Speedup: {speedup_canyon:>8.2f}×")
        print(f"   Fitness difference: {abs(fitness_scipy - fitness_jit):.6f}")
        
        # Comparison
        print_subheader("COMPARISON")
        print(f"   Simple Porosity (scipy):     {time_simple_scipy:>8.4f} ms")
        print(f"   Simple Porosity (JIT):       {time_simple_jit:>8.4f} ms  ({speedup_simple:.2f}× {'faster' if speedup_simple > 1 else 'slower'})")
        print(f"   Street Canyon (scipy):       {time_canyon_scipy:>8.4f} ms")
        print(f"   Street Canyon (JIT):         {time_canyon_jit:>8.4f} ms  ({speedup_canyon:.2f}× {'faster' if speedup_canyon > 1 else 'slower'})")
        print(f"   ---")
        print(f"   Canyon vs Simple (scipy):    {time_canyon_scipy/time_simple_scipy:.2f}× slower")
        print(f"   Canyon vs Simple (JIT):      {time_canyon_jit/time_simple_jit:.2f}× slower")
    
    # Summary comparison
    print_header("SUMMARY: FITNESS FUNCTION SCALING")
    
    print("\n" + "=" * 100)
    print("ABSOLUTE TIMINGS (ms)")
    print("=" * 100)
    print(f"{'Parcel Size':<15} {'Grid':<10} {'Simple (scipy)':>15} {'Simple (JIT)':>15} {'Canyon (scipy)':>15} {'Canyon (JIT)':>15}")
    print("-" * 100)
    
    for i, config in enumerate(PARCEL_CONFIGS):
        print(f"{config['name']:<15} {config['grid_size']:>3}²      "
              f"{results['simple_scipy'][i]:>15.4f} {results['simple_jit'][i]:>15.4f} "
              f"{results['canyon_scipy'][i]:>15.4f} {results['canyon_jit'][i]:>15.4f}")
    
    print("\n" + "=" * 100)
    print("SPEEDUP FACTORS (JIT vs scipy)")
    print("=" * 100)
    print(f"{'Parcel Size':<15} {'Grid':<10} {'Simple Porosity':>20} {'Street Canyon':>20}")
    print("-" * 100)
    
    for i, config in enumerate(PARCEL_CONFIGS):
        speedup_simple = results['simple_scipy'][i] / results['simple_jit'][i]
        speedup_canyon = results['canyon_scipy'][i] / results['canyon_jit'][i]
        print(f"{config['name']:<15} {config['grid_size']:>3}²      "
              f"{speedup_simple:>19.2f}× {speedup_canyon:>19.2f}×")
    
    print("\n" + "=" * 100)
    print("SCALING FACTORS (relative to 50m×50m parcel)")
    print("=" * 100)
    print(f"{'Parcel Size':<15} {'Pixels':<12} {'Simple (scipy)':>15} {'Simple (JIT)':>15} {'Canyon (scipy)':>15} {'Canyon (JIT)':>15}")
    print("-" * 100)
    
    base_pixels = PARCEL_CONFIGS[0]['grid_size'] ** 2
    for i, config in enumerate(PARCEL_CONFIGS):
        pixels = config['grid_size'] ** 2
        pixel_ratio = pixels / base_pixels
        
        scale_simple_scipy = results['simple_scipy'][i] / results['simple_scipy'][0]
        scale_simple_jit = results['simple_jit'][i] / results['simple_jit'][0]
        scale_canyon_scipy = results['canyon_scipy'][i] / results['canyon_scipy'][0]
        scale_canyon_jit = results['canyon_jit'][i] / results['canyon_jit'][0]
        
        print(f"{config['name']:<15} {pixel_ratio:>10.1f}×  "
              f"{scale_simple_scipy:>14.2f}× {scale_simple_jit:>14.2f}× "
              f"{scale_canyon_scipy:>14.2f}× {scale_canyon_jit:>14.2f}×")
    
    # Complexity analysis
    print("\n" + "=" * 100)
    print("COMPLEXITY ANALYSIS")
    print("=" * 100)
    
    print("\nTheoretical complexity for N×N×H grid:")
    print("  - scipy.ndimage.rotate():  O(N² × H) - spline interpolation on 3D volume")
    print("  - Manual rotation (JIT):   O(N² × H) - nearest neighbor sampling")
    print("  - Simple porosity calc:    O(N² × H) - scan all voxels")
    print("  - Street canyon calc:      O(N² × H) - multiple passes over volume")
    
    # Calculate observed complexity
    if len(PARCEL_CONFIGS) >= 2:
        pixel_ratio = (PARCEL_CONFIGS[-1]['grid_size'] / PARCEL_CONFIGS[0]['grid_size']) ** 2
        
        print("\nObserved scaling (50m → 500m):")
        print(f"  Pixel ratio: {pixel_ratio:.1f}×")
        
        for name, label in [('simple_scipy', 'Simple (scipy)'),
                            ('simple_jit', 'Simple (JIT)'),
                            ('canyon_scipy', 'Canyon (scipy)'),
                            ('canyon_jit', 'Canyon (JIT)')]:
            time_ratio = results[name][-1] / results[name][0]
            # N^x = time_ratio => x = log(time_ratio) / log(pixel_ratio^0.5)
            complexity = np.log(time_ratio) / np.log(pixel_ratio)
            print(f"  {label:<20} Time ratio: {time_ratio:>6.2f}×  →  O(N^{complexity:.2f})")
    
    print("\n" + "=" * 100)
    print("RECOMMENDATIONS")
    print("=" * 100)
    
    print("\n✓ SIMPLE POROSITY:")
    avg_speedup_simple = np.mean([results['simple_scipy'][i] / results['simple_jit'][i] 
                                  for i in range(len(PARCEL_CONFIGS))])
    if avg_speedup_simple > 1.2:
        print(f"  → USE JIT VERSION (average {avg_speedup_simple:.2f}× faster)")
    else:
        print(f"  → USE SCIPY VERSION (JIT only {avg_speedup_simple:.2f}× faster, not worth complexity)")
    
    print("\n✓ STREET CANYON:")
    avg_speedup_canyon = np.mean([results['canyon_scipy'][i] / results['canyon_jit'][i] 
                                  for i in range(len(PARCEL_CONFIGS))])
    if avg_speedup_canyon > 1.2:
        print(f"  → USE JIT VERSION (average {avg_speedup_canyon:.2f}× faster)")
    else:
        print(f"  → USE SCIPY VERSION (JIT only {avg_speedup_canyon:.2f}× faster, not worth complexity)")
    
    # Check if rotation is the bottleneck
    print("\n✓ BOTTLENECK ANALYSIS:")
    print(f"  At 500m parcel:")
    print(f"    Simple scipy: {results['simple_scipy'][-1]:.2f} ms")
    print(f"    Simple JIT:   {results['simple_jit'][-1]:.2f} ms")
    if results['simple_scipy'][-1] > results['simple_jit'][-1] * 2:
        print(f"  → scipy.ndimage.rotate() is a MAJOR bottleneck at large scales")
    else:
        print(f"  → scipy.ndimage.rotate() overhead is acceptable")
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
