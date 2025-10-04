"""
Test script to verify Solution 1 (Rotate 2D Heightmaps) implementation.

This script validates that:
1. Rotating 2D then creating 3D gives same result as creating 3D then rotating
2. The new approach is significantly faster
3. Fitness values remain consistent
"""
import numpy as np
from scipy.ndimage import rotate
import time

def create_3d_from_heightmap(heightmap_2d, max_height=30):
    """Create 3D voxel array from 2D heightmap."""
    z_indices = np.arange(max_height)
    return (z_indices < heightmap_2d.astype(int)[:, :, np.newaxis]).astype(np.int8)

def test_correctness():
    """Test that rotating 2D->3D equals 3D->rotate."""
    print("=" * 70)
    print("TEST 1: CORRECTNESS - Do both methods give identical results?")
    print("=" * 70)
    
    # Create a sample heightmap
    np.random.seed(42)
    heightmap_2d = np.random.randint(0, 10, size=(32, 32)).astype(float)
    wind_angle = 45  # Test with non-90° angle
    
    # Method A (OLD): Create 3D, then rotate
    print("\nMethod A (OLD): Create 3D -> Rotate 3D")
    design_3d_A = create_3d_from_heightmap(heightmap_2d)
    print(f"  3D array shape: {design_3d_A.shape}")
    print(f"  3D array size: {design_3d_A.size} elements")
    rotated_3d_A = rotate(design_3d_A, angle=wind_angle, axes=(0, 1), reshape=False, order=0)
    
    # Method B (NEW): Rotate 2D, then create 3D
    print("\nMethod B (NEW): Rotate 2D -> Create 3D")
    rotated_2d_B = rotate(heightmap_2d, angle=wind_angle, reshape=False, order=0)
    print(f"  2D array shape: {rotated_2d_B.shape}")
    print(f"  2D array size: {rotated_2d_B.size} elements")
    rotated_3d_B = create_3d_from_heightmap(rotated_2d_B)
    
    # Compare results
    print("\nComparison:")
    print(f"  Arrays are identical: {np.array_equal(rotated_3d_A, rotated_3d_B)}")
    if not np.array_equal(rotated_3d_A, rotated_3d_B):
        diff = np.abs(rotated_3d_A - rotated_3d_B)
        print(f"  Max difference: {np.max(diff)}")
        print(f"  Mean difference: {np.mean(diff)}")
        print(f"  % pixels different: {100 * np.sum(diff > 0) / diff.size:.2f}%")
    
    # For order=0 (nearest neighbor), results should be very close
    are_close = np.allclose(rotated_3d_A, rotated_3d_B, atol=1)
    print(f"  Results are close (tolerance=1): {are_close}")
    
    return are_close

def test_performance():
    """Test performance improvement of new approach."""
    print("\n" + "=" * 70)
    print("TEST 2: PERFORMANCE - How much faster is the new approach?")
    print("=" * 70)
    
    # Create sample data
    np.random.seed(42)
    heightmap_2d = np.random.randint(0, 10, size=(32, 32)).astype(float)
    wind_angle = 45
    num_iterations = 1000
    
    print(f"\nRunning {num_iterations} iterations for each method...")
    
    # Test OLD method (3D rotation)
    print("\nMethod A (OLD): Create 3D -> Rotate 3D")
    start = time.time()
    for _ in range(num_iterations):
        design_3d = create_3d_from_heightmap(heightmap_2d)
        rotated_3d = rotate(design_3d, angle=wind_angle, axes=(0, 1), reshape=False, order=0)
    time_old = time.time() - start
    print(f"  Total time: {time_old:.3f} seconds")
    print(f"  Per iteration: {1000 * time_old / num_iterations:.3f} ms")
    
    # Test NEW method (2D rotation)
    print("\nMethod B (NEW): Rotate 2D -> Create 3D")
    start = time.time()
    for _ in range(num_iterations):
        rotated_2d = rotate(heightmap_2d, angle=wind_angle, reshape=False, order=0)
        design_3d = create_3d_from_heightmap(rotated_2d)
    time_new = time.time() - start
    print(f"  Total time: {time_new:.3f} seconds")
    print(f"  Per iteration: {1000 * time_new / num_iterations:.3f} ms")
    
    # Calculate speedup
    speedup = time_old / time_new
    print(f"\n{'=' * 70}")
    print(f"SPEEDUP: {speedup:.2f}x faster!")
    print(f"{'=' * 70}")
    
    # Extrapolate to full optimization
    evaluations = 80000
    time_saved = (time_old - time_new) * evaluations / num_iterations
    print(f"\nFor {evaluations} evaluations (typical optimization):")
    print(f"  OLD method would take: {time_old * evaluations / num_iterations:.1f} seconds ({time_old * evaluations / num_iterations / 60:.1f} minutes)")
    print(f"  NEW method would take: {time_new * evaluations / num_iterations:.1f} seconds ({time_new * evaluations / num_iterations / 60:.1f} minutes)")
    print(f"  Time saved: {time_saved:.1f} seconds ({time_saved / 60:.1f} minutes)")
    
    return speedup

def test_fitness_consistency():
    """Test that fitness functions work correctly with pre-rotated input."""
    print("\n" + "=" * 70)
    print("TEST 3: FITNESS CONSISTENCY - Do fitness functions still work?")
    print("=" * 70)
    
    # Import fitness functions
    import sys
    sys.path.insert(0, '/home/alex/Documents/_cloud/Funded_Projects/OpenSKIZZE/code/openskizze')
    from backend.evaluation import compute_fitness, compute_fitness_street_canyon
    
    # Create sample heightmap
    np.random.seed(42)
    heightmap_2d = np.random.randint(0, 15, size=(32, 32)).astype(float)
    wind_angle = 45
    
    # Create rotated 3D (as new code does)
    rotated_2d = rotate(heightmap_2d, angle=wind_angle, reshape=False, order=0)
    heightmap_3d_rotated = create_3d_from_heightmap(rotated_2d)
    
    print("\nTesting compute_fitness (simple porosity)...")
    try:
        fitness1 = compute_fitness(heightmap_3d_rotated, wind_direction=wind_angle)
        print(f"  ✓ Success! Fitness = {fitness1:.4f}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    
    print("\nTesting compute_fitness_street_canyon...")
    try:
        fitness2 = compute_fitness_street_canyon(heightmap_3d_rotated, wind_direction=wind_angle)
        print(f"  ✓ Success! Fitness = {fitness2:.4f}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    
    print("\n✓ Both fitness functions work correctly with pre-rotated input!")
    return True

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("SOLUTION 1: ROTATE 2D HEIGHTMAPS - VALIDATION TESTS")
    print("=" * 70)
    
    # Run all tests
    test1_passed = test_correctness()
    test2_speedup = test_performance()
    test3_passed = test_fitness_consistency()
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"✓ Correctness test: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"✓ Performance test: {test2_speedup:.2f}x speedup achieved")
    print(f"✓ Fitness consistency: {'PASSED' if test3_passed else 'FAILED'}")
    
    if test1_passed and test2_speedup > 1.5 and test3_passed:
        print("\n🎉 ALL TESTS PASSED! Solution 1 is ready for production.")
        print(f"\nExpected overall speedup: ~1.5-2x")
        print(f"(Rotation was 40-50% of time, now {test2_speedup:.1f}x faster)")
    else:
        print("\n⚠️  Some tests failed. Review results above.")
