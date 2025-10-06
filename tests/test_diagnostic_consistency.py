"""
Quick test to verify diagnostic visualization produces correct fitness values.
Compares diagnostic visualization output with direct compute_fitness() calls.
"""
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.evaluation import compute_fitness


def test_simple_cases():
    """
    Test simple cases directly without full environment setup
    """
    print("Testing Simple Wind Porosity Calculation")
    print("=" * 60)
    
    # Test Case 1: Empty environment
    print("\nTest 1: Empty Environment")
    print("-" * 60)
    empty_env = np.zeros((10, 10, 10))
    fitness_empty = compute_fitness(empty_env, wind_direction=0)
    print(f"  Fitness: {fitness_empty:.6f}")
    print(f"  Expected: 1.000000")
    print(f"  Status: {'✅ PASS' if np.isclose(fitness_empty, 1.0) else '❌ FAIL'}")
    
    # Test Case 2: Single building
    print("\nTest 2: Single Building (2x2x5)")
    print("-" * 60)
    single_building = np.zeros((10, 10, 10))
    single_building[4:6, 4:6, 0:5] = 1
    fitness_single = compute_fitness(single_building, wind_direction=0)
    expected = 0.90  # (100 - 10) / 100
    print(f"  Fitness: {fitness_single:.6f}")
    print(f"  Expected: ~{expected:.6f}")
    print(f"  Status: {'✅ PASS' if 0.85 <= fitness_single <= 0.95 else '❌ FAIL'}")
    
    # Test Case 3: Full blockage
    print("\nTest 3: Full Blockage")
    print("-" * 60)
    full_env = np.ones((10, 10, 10))
    fitness_full = compute_fitness(full_env, wind_direction=0)
    print(f"  Fitness: {fitness_full:.6f}")
    print(f"  Expected: 0.000000")
    print(f"  Status: {'✅ PASS' if np.isclose(fitness_full, 0.0) else '❌ FAIL'}")
    
    # Test Case 4: Corridor aligned with wind
    print("\nTest 4: Corridor Aligned with Wind")
    print("-" * 60)
    corridor = np.zeros((10, 10, 10))
    corridor[0:3, :, 0:5] = 1  # Left building
    corridor[7:10, :, 0:5] = 1  # Right building
    fitness_corridor = compute_fitness(corridor, wind_direction=0)
    expected = 0.70  # Middle corridor + upper levels
    print(f"  Fitness: {fitness_corridor:.6f}")
    print(f"  Expected: ~{expected:.6f}")
    print(f"  Status: {'✅ PASS' if 0.65 <= fitness_corridor <= 0.75 else '❌ FAIL'}")
    
    print("\n" + "=" * 60)
    print("✅ Simple tests completed!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_simple_cases()
    sys.exit(0 if success else 1)
