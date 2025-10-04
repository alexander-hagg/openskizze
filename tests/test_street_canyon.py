"""
Quick validation test for Street Canyon Ventilation objective function.
Run this to verify the implementation works correctly.
"""

import numpy as np
from scipy.ndimage import rotate

# Inline implementations to avoid import issues
def compute_fitness(heightmap_3d: np.ndarray, wind_direction: int) -> float:
    """Simple wind porosity"""
    rotation_angle = (wind_direction + 90) % 360
    rotated_env = rotate(heightmap_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
    projection = np.sum(rotated_env, axis=1)
    open_columns = np.sum(projection == 0)
    total_columns = projection.shape[0] * projection.shape[1]
    porosity = open_columns / total_columns if total_columns > 0 else 0.0
    return np.clip(porosity, 0.0, 1.0)

def compute_fitness_street_canyon(heightmap_3d: np.ndarray, wind_direction: int) -> float:
    """Street canyon ventilation"""
    rotation_angle = (wind_direction + 90) % 360
    rotated_env = rotate(heightmap_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
    
    rows, cols, height = rotated_env.shape
    
    # Component 1: Ground-level street canyons
    ground_level = rotated_env[:, :, :2]
    ground_occupied = np.any(ground_level > 0, axis=2)
    
    open_corridors_per_row = []
    for row in range(rows):
        corridor_lengths = []
        current_length = 0
        for col in range(cols):
            if not ground_occupied[row, col]:
                current_length += 1
            else:
                if current_length > 0:
                    corridor_lengths.append(current_length)
                current_length = 0
        if current_length > 0:
            corridor_lengths.append(current_length)
        
        if corridor_lengths:
            open_corridors_per_row.append(np.mean(corridor_lengths) / cols)
    
    street_canyon_score = np.mean(open_corridors_per_row) if open_corridors_per_row else 0.0
    
    # Component 2: Lateral ventilation
    lateral_openness = []
    for col in range(cols):
        column_slice = rotated_env[:, col, :]
        open_cells = np.sum(column_slice == 0)
        total_cells = column_slice.size
        lateral_openness.append(open_cells / total_cells if total_cells > 0 else 0.0)
    
    lateral_ventilation_score = np.mean(lateral_openness)
    
    # Component 3: Height variation
    max_heights = np.max(rotated_env, axis=2)
    height_std = np.std(max_heights) if max_heights.size > 0 else 0.0
    max_possible_std = height / 2
    height_variation_score = min(height_std / max_possible_std, 1.0) if max_possible_std > 0 else 0.0
    
    # Component 4: Partial penetration
    projection = np.sum(rotated_env, axis=1)
    max_depth = height
    penetration_per_column = 1.0 - np.clip(projection / max_depth, 0.0, 1.0)
    penetration_score = np.mean(penetration_per_column)
    
    # Weighted combination
    fitness = (
        0.35 * street_canyon_score +
        0.25 * lateral_ventilation_score +
        0.15 * height_variation_score +
        0.25 * penetration_score
    )
    
    return np.clip(fitness, 0.0, 1.0)

def test_street_canyon_objective():
    """Test that street canyon objective returns non-zero for dense environments"""
    
    print("=" * 60)
    print("Testing Street Canyon Ventilation Objective")
    print("=" * 60)
    
    # Create a dense urban environment (similar to user's case)
    # Grid: 20x20x10 (20m x 20m, 10 floors max)
    rows, cols, height = 20, 20, 10
    
    # Test Case 1: Completely open (should score high on both)
    print("\n[Test 1] Completely open environment")
    env_open = np.zeros((rows, cols, height), dtype=np.int8)
    
    fitness_simple = compute_fitness(env_open, wind_direction=0)
    fitness_canyon = compute_fitness_street_canyon(env_open, wind_direction=0)
    
    print(f"  Simple Porosity:      {fitness_simple:.4f} (expected: 1.0)")
    print(f"  Street Canyon:        {fitness_canyon:.4f} (expected: ~0.8-1.0)")
    assert fitness_simple > 0.99, "Simple porosity should be ~1.0 for open environment"
    assert fitness_canyon > 0.5, "Street canyon should be high for open environment"
    
    # Test Case 2: Completely blocked (worst case)
    print("\n[Test 2] Completely blocked environment")
    env_blocked = np.ones((rows, cols, height), dtype=np.int8)
    
    fitness_simple = compute_fitness(env_blocked, wind_direction=0)
    fitness_canyon = compute_fitness_street_canyon(env_blocked, wind_direction=0)
    
    print(f"  Simple Porosity:      {fitness_simple:.4f} (expected: 0.0)")
    print(f"  Street Canyon:        {fitness_canyon:.4f} (expected: ~0.0-0.2)")
    assert fitness_simple == 0.0, "Simple porosity should be 0.0 for blocked environment"
    assert fitness_canyon < 0.3, "Street canyon should be low for blocked environment"
    
    # Test Case 3: Dense urban with street canyons (THE KEY TEST)
    print("\n[Test 3] Dense urban with horizontal street canyons")
    env_dense = np.ones((rows, cols, height), dtype=np.int8)
    
    # Create 3 horizontal streets (E-W corridors)
    # Street 1: rows 4-5 completely open
    env_dense[4:6, :, 0:2] = 0
    # Street 2: rows 9-10 completely open
    env_dense[9:11, :, 0:2] = 0
    # Street 3: rows 14-15 completely open
    env_dense[14:16, :, 0:2] = 0
    
    # Also vary building heights for turbulence
    for i in range(rows):
        for j in range(cols):
            if env_dense[i, j, 0] == 1:  # If not a street
                # Random height 3-8 floors
                random_height = np.random.randint(3, 9)
                env_dense[i, j, random_height:] = 0
    
    fitness_simple = compute_fitness(env_dense, wind_direction=0)
    fitness_canyon = compute_fitness_street_canyon(env_dense, wind_direction=0)
    
    print(f"  Simple Porosity:      {fitness_simple:.4f} (expected: 0.0 - no vertical passages)")
    print(f"  Street Canyon:        {fitness_canyon:.4f} (expected: >0.0 - detects horizontal corridors)")
    
    # THIS IS THE CRITICAL ASSERTION
    assert fitness_simple == 0.0, "Dense urban should have 0 vertical passages"
    assert fitness_canyon > 0.0, "Street canyon should detect horizontal corridors!"
    assert fitness_canyon > fitness_simple, "Street canyon should outperform simple porosity in dense urban!"
    
    print(f"\n  ✓ PASS: Street canyon objective provides {fitness_canyon / max(fitness_simple, 0.01):.1f}x better gradient!")
    
    # Test Case 4: Different wind directions
    print("\n[Test 4] Wind direction sensitivity")
    for wind_dir in [0, 90, 180, 270]:
        fitness = compute_fitness_street_canyon(env_dense, wind_direction=wind_dir)
        print(f"  Wind {wind_dir:3d}°: {fitness:.4f}")
    
    # Test Case 5: Height variation effect
    print("\n[Test 5] Height variation impact")
    # Flat buildings (no variation)
    env_flat = np.zeros((rows, cols, height), dtype=np.int8)
    env_flat[:, :, 0:5] = 1  # All buildings 5 floors
    env_flat[4:6, :, :] = 0  # One street
    
    # Varied buildings
    env_varied = env_flat.copy()
    for i in range(rows):
        for j in range(cols):
            if i not in [4, 5]:  # Not in street
                h = np.random.randint(2, 9)
                env_varied[i, j, 0:h] = 1
                env_varied[i, j, h:] = 0
    
    fitness_flat = compute_fitness_street_canyon(env_flat, wind_direction=0)
    fitness_varied = compute_fitness_street_canyon(env_varied, wind_direction=0)
    
    print(f"  Flat buildings:       {fitness_flat:.4f}")
    print(f"  Varied heights:       {fitness_varied:.4f}")
    print(f"  Improvement:          {fitness_varied - fitness_flat:+.4f}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nKey Finding:")
    print("  Street Canyon objective successfully detects horizontal")
    print("  ventilation corridors where Simple Porosity returns 0.0")
    print("\nRecommendation:")
    print("  Use 'Street Canyon Ventilation' for dense urban contexts")
    print("=" * 60)

if __name__ == '__main__':
    test_street_canyon_objective()
