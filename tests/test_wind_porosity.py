"""
Test suite for compute_fitness function with visualizations.
Tests horizontal wind porosity calculation with simple, interpretable cases.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d import Axes3D
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.evaluation import compute_fitness


def visualize_test_case(heightmap_3d, wind_direction, fitness, test_name, ax_3d, ax_top, ax_side):
    """
    Visualize a test case in 3D and 2D projections.
    
    Args:
        heightmap_3d: 3D numpy array (x, y, z)
        wind_direction: Wind direction in degrees
        fitness: Computed fitness value
        test_name: Name of the test
        ax_3d: 3D axis for voxel plot
        ax_top: 2D axis for top view
        ax_side: 2D axis for side view (wind direction)
    """
    rows, cols, height = heightmap_3d.shape
    
    # 3D Voxel visualization
    colors = np.empty(heightmap_3d.shape, dtype=object)
    colors[heightmap_3d > 0] = 'red'
    ax_3d.voxels(heightmap_3d > 0, facecolors=colors, edgecolor='k', alpha=0.7)
    
    # Add wind direction arrow
    arrow_length = max(rows, cols) * 0.4
    wind_rad = np.radians(wind_direction)
    dx = arrow_length * np.sin(wind_rad)
    dy = arrow_length * np.cos(wind_rad)
    ax_3d.quiver(rows/2, cols/2, 0, dx, dy, 0, color='blue', arrow_length_ratio=0.3, linewidth=3, label='Wind')
    
    ax_3d.set_xlabel('X')
    ax_3d.set_ylabel('Y')
    ax_3d.set_zlabel('Z (Height)')
    ax_3d.set_title(f'{test_name}\nFitness: {fitness:.3f}', fontsize=10, fontweight='bold')
    ax_3d.set_xlim([0, rows])
    ax_3d.set_ylim([0, cols])
    ax_3d.set_zlim([0, height])
    
    # Top view (X-Y plane)
    max_height_map = np.max(heightmap_3d, axis=2)
    ax_top.imshow(max_height_map.T, origin='lower', cmap='Reds', vmin=0, vmax=height)
    ax_top.set_title('Top View', fontsize=9)
    ax_top.set_xlabel('X')
    ax_top.set_ylabel('Y')
    
    # Add wind direction arrow on top view
    arrow_scale = 0.3
    ax_top.arrow(rows/2, cols/2, dx*arrow_scale, dy*arrow_scale, 
                 head_width=0.5, head_length=0.5, fc='blue', ec='blue', linewidth=2)
    ax_top.text(rows/2 + dx*arrow_scale*1.3, cols/2 + dy*arrow_scale*1.3, 
                'Wind', color='blue', fontsize=8, fontweight='bold')
    
    # Side view along wind direction (after rotation)
    rotation_angle = wind_direction % 360
    from scipy.ndimage import rotate as scipy_rotate
    rotated_env = scipy_rotate(heightmap_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
    
    # Project along Y-axis (wind direction)
    side_projection = np.max(rotated_env, axis=1)  # Shape: (rows, height)
    ax_side.imshow(side_projection.T, origin='lower', cmap='Reds', aspect='auto', vmin=0, vmax=1)
    ax_side.set_title(f'Side View (Wind Direction)\nBlocked paths in red', fontsize=9)
    ax_side.set_xlabel('X (perpendicular to wind)')
    ax_side.set_ylabel('Z (Height)')
    
    # Mark open paths with green dots
    open_paths = side_projection == 0
    for x in range(side_projection.shape[0]):
        for z in range(side_projection.shape[1]):
            if open_paths[x, z]:
                ax_side.plot(x, z, 'go', markersize=4, alpha=0.6)


def test_empty_environment():
    """Test 1: Empty environment - should return 1.0"""
    heightmap = np.zeros((10, 10, 10))
    fitness = compute_fitness(heightmap, wind_direction=0)
    print(f"Test 1 - Empty environment: {fitness:.3f} (expected: 1.000)")
    assert np.isclose(fitness, 1.0), f"Expected 1.0, got {fitness}"
    return heightmap, fitness, "Test 1: Empty Environment"


def test_single_building_center():
    """Test 2: Single building in center - should block some paths"""
    heightmap = np.zeros((10, 10, 10))
    heightmap[4:6, 4:6, 0:5] = 1  # 2x2 building, 5 units tall
    fitness = compute_fitness(heightmap, wind_direction=0)
    # Expected: (10*10 - 2*5) / (10*10) = 90/100 = 0.90
    expected = 0.90
    print(f"Test 2 - Single building center: {fitness:.3f} (expected: ~{expected:.3f})")
    assert 0.85 <= fitness <= 0.95, f"Expected ~{expected}, got {fitness}"
    return heightmap, fitness, "Test 2: Single Building (Center)"


def test_wall_perpendicular_to_wind():
    """Test 3: Wall perpendicular to wind - should block all paths at that height"""
    heightmap = np.zeros((10, 10, 10))
    heightmap[4:5, :, 0:3] = 1  # Wall across entire Y-axis, 3 units tall
    fitness = compute_fitness(heightmap, wind_direction=0)
    # Expected: (10*10 - 1*3) / (10*10) = 97/100 = 0.97
    expected = 0.97
    print(f"Test 3 - Wall perpendicular to wind: {fitness:.3f} (expected: ~{expected:.3f})")
    assert 0.95 <= fitness <= 0.99, f"Expected ~{expected}, got {fitness}"
    return heightmap, fitness, "Test 3: Wall Perpendicular to Wind"


def test_wall_parallel_to_wind():
    """Test 4: Wall parallel to wind - should not block wind paths"""
    heightmap = np.zeros((10, 10, 10))
    heightmap[:, 4:5, 0:3] = 1  # Wall along entire X-axis, 3 units tall
    fitness = compute_fitness(heightmap, wind_direction=0)
    # Expected: Wall is parallel, so wind flows around it
    # Only blocks: 10 (x positions) * 3 (heights) = 30 paths
    expected = 0.70
    print(f"Test 4 - Wall parallel to wind: {fitness:.3f} (expected: ~{expected:.3f})")
    assert 0.65 <= fitness <= 0.75, f"Expected ~{expected}, got {fitness}"
    return heightmap, fitness, "Test 4: Wall Parallel to Wind"


def test_full_blockage():
    """Test 5: Completely filled environment - should return 0.0"""
    heightmap = np.ones((10, 10, 10))
    fitness = compute_fitness(heightmap, wind_direction=0)
    print(f"Test 5 - Full blockage: {fitness:.3f} (expected: 0.000)")
    assert np.isclose(fitness, 0.0), f"Expected 0.0, got {fitness}"
    return heightmap, fitness, "Test 5: Full Blockage"


def test_corridor_with_wind():
    """Test 6: Corridor aligned with wind - should have high porosity"""
    heightmap = np.zeros((10, 10, 10))
    # Create buildings on sides, leaving corridor in middle
    heightmap[0:3, :, 0:5] = 1  # Left building
    heightmap[7:10, :, 0:5] = 1  # Right building
    fitness = compute_fitness(heightmap, wind_direction=0)
    # Expected: Middle 4 columns free at all 10 heights + top 5 heights of blocked columns
    # Free: 4*10 + 3*5 + 3*5 = 40 + 15 + 15 = 70 / 100 = 0.70
    expected = 0.70
    print(f"Test 6 - Corridor with wind: {fitness:.3f} (expected: ~{expected:.3f})")
    assert 0.65 <= fitness <= 0.75, f"Expected ~{expected}, got {fitness}"
    return heightmap, fitness, "Test 6: Corridor Aligned with Wind"


def test_corridor_against_wind():
    """Test 7: Corridor perpendicular to wind - should have low porosity"""
    heightmap = np.zeros((10, 10, 10))
    # Create buildings top/bottom, leaving corridor in middle
    heightmap[:, 0:3, 0:5] = 1  # Bottom building
    heightmap[:, 7:10, 0:5] = 1  # Top building
    fitness = compute_fitness(heightmap, wind_direction=0)
    # Expected: Wind must pass through buildings, all X positions blocked at ground level
    expected = 0.50  # Only upper heights are free
    print(f"Test 7 - Corridor perpendicular to wind: {fitness:.3f} (expected: ~{expected:.3f})")
    assert 0.45 <= fitness <= 0.55, f"Expected ~{expected}, got {fitness}"
    return heightmap, fitness, "Test 7: Corridor Perpendicular to Wind"


def test_wind_direction_sensitivity():
    """Test 8: Same buildings, different wind directions"""
    heightmap = np.zeros((10, 10, 10))
    heightmap[2:4, 4:6, 0:3] = 1  # Building 1
    heightmap[6:8, 4:6, 0:3] = 1  # Building 2
    
    results = []
    for wind_dir in [0, 45, 90, 180, 270]:
        fitness = compute_fitness(heightmap, wind_direction=wind_dir)
        results.append((wind_dir, fitness))
        print(f"Test 8 - Wind direction {wind_dir}°: {fitness:.3f}")
    
    # Check that different directions give different results
    fitness_values = [f for _, f in results]
    assert len(set(fitness_values)) > 1, "Wind direction should affect fitness"
    
    return heightmap, results[0][1], f"Test 8: Wind Direction 0°"


def run_all_tests_with_visualization():
    """Run all tests and create comprehensive visualization"""
    tests = [
        test_empty_environment,
        test_single_building_center,
        test_wall_perpendicular_to_wind,
        test_wall_parallel_to_wind,
        test_full_blockage,
        test_corridor_with_wind,
        test_corridor_against_wind,
        test_wind_direction_sensitivity,
    ]
    
    n_tests = len(tests)
    fig = plt.figure(figsize=(20, 4 * n_tests))
    
    for i, test_func in enumerate(tests):
        print(f"\n{'='*60}")
        heightmap, fitness, test_name = test_func()
        print(f"{'='*60}")
        
        # Create subplots for this test
        ax_3d = fig.add_subplot(n_tests, 3, i*3 + 1, projection='3d')
        ax_top = fig.add_subplot(n_tests, 3, i*3 + 2)
        ax_side = fig.add_subplot(n_tests, 3, i*3 + 3)
        
        visualize_test_case(heightmap, wind_direction=0, fitness=fitness, 
                          test_name=test_name, ax_3d=ax_3d, ax_top=ax_top, ax_side=ax_side)
    
    plt.tight_layout()
    
    # Save the figure
    output_path = os.path.join(os.path.dirname(__file__), '..', 'debug_plots', 'wind_porosity_tests.png')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n{'='*60}")
    print(f"Visualization saved to: {output_path}")
    print(f"{'='*60}")
    
    plt.show()
    
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    run_all_tests_with_visualization()
