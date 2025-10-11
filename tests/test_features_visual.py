"""
Test script for validating feature calculations for both feature sets.
Creates visualizations to manually verify feature implementations.

Run with:
    python tests/test_features_visual.py
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.evaluation import calculate_all_features, calculate_all_features_planning
from backend.config import DOMAIN_CONFIG
from scipy.ndimage import label


def create_test_heightmaps():
    """Create various test heightmaps to validate feature calculations."""
    
    # Test 1: Simple single building
    test1 = np.zeros((20, 20))
    test1[8:12, 8:12] = 15  # 4x4 building, 15m tall
    
    # Test 2: Two buildings with different heights
    test2 = np.zeros((20, 20))
    test2[5:9, 5:9] = 12  # 4x4 building, 12m tall
    test2[11:15, 11:15] = 24  # 4x4 building, 24m tall
    
    # Test 3: Street canyon configuration
    test3 = np.zeros((30, 30))
    test3[5:25, 5:10] = 18  # Tall building on one side
    test3[5:25, 20:25] = 18  # Tall building on other side
    # Street canyon in between (10 pixels wide = 30m)
    
    # Test 4: Dense urban configuration
    test4 = np.zeros((30, 30))
    test4[2:8, 2:8] = 15
    test4[2:8, 10:16] = 18
    test4[2:8, 18:24] = 21
    test4[10:16, 2:8] = 12
    test4[10:16, 10:16] = 24
    test4[10:16, 18:24] = 15
    test4[18:24, 2:8] = 18
    test4[18:24, 10:16] = 15
    test4[18:24, 18:24] = 21
    
    # Test 5: Sparse suburban
    test5 = np.zeros((30, 30))
    test5[5:8, 5:10] = 9  # Small building
    test5[5:8, 20:25] = 9
    test5[20:23, 5:10] = 12
    test5[20:23, 20:25] = 6
    
    return {
        'Single Building': test1,
        'Two Buildings': test2,
        'Street Canyon': test3,
        'Dense Urban': test4,
        'Sparse Suburban': test5
    }


def visualize_heightmap(ax, heightmap, title):
    """Visualize a heightmap with height information."""
    im = ax.imshow(heightmap, cmap='viridis', origin='lower')
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.set_xlabel('X (pixels)', fontsize=8)
    ax.set_ylabel('Y (pixels)', fontsize=8)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Height (m)', fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    
    # Add grid
    ax.grid(True, alpha=0.3, linewidth=0.5)
    ax.tick_params(labelsize=7)


def test_feature_calculations():
    """Test and visualize feature calculations for both feature sets."""
    
    test_cases = create_test_heightmaps()
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    
    # Create output directory
    output_dir = 'debug_plots'
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*80)
    print("FEATURE CALCULATION TESTS")
    print("="*80)
    
    for test_name, heightmap in test_cases.items():
        print(f"\n{'='*80}")
        print(f"Test Case: {test_name}")
        print(f"{'='*80}")
        print(f"Grid size: {heightmap.shape}")
        print(f"Pixel size: {pixel_size}m")
        
        # Create buildable mask (all pixels buildable for these tests)
        buildable_mask = np.ones_like(heightmap, dtype=bool)
        buildable_area_m2 = np.sum(buildable_mask) * (pixel_size ** 2)
        print(f"Buildable area: {buildable_area_m2:.0f} m²")
        
        # Calculate features for both sets
        features_original = calculate_all_features(heightmap, buildable_mask, buildable_area_m2)
        features_planning = calculate_all_features_planning(heightmap, buildable_mask, buildable_area_m2)
        
        # Print original features
        print(f"\n--- ORIGINAL FEATURES ---")
        feature_names_orig = [
            'Built Area (m²)', 'Avg Height (m)', 'Height Variability (m)',
            'Num Buildings', 'Avg Distance (m)', 'Gross Floor Area (m²)',
            'Building Mass X', 'Building Mass Y'
        ]
        for i, (name, value) in enumerate(zip(feature_names_orig, features_original)):
            print(f"  [{i}] {name:25s}: {value:10.2f}")
        
        # Print planning features
        print(f"\n--- PLANNING FEATURES (BACKLOG) ---")
        feature_names_planning = [
            'GRZ (ratio)', 'GFZ (ratio)', 'Avg Height (m)', 'Height Variability (m)',
            'Num Buildings', 'Avg Distance (m)', 'Street Canyon H/W', 'SVF (approx)'
        ]
        for i, (name, value) in enumerate(zip(feature_names_planning, features_planning)):
            print(f"  [{i}] {name:25s}: {value:10.2f}")
        
        # Verify some basic properties
        print(f"\n--- SANITY CHECKS ---")
        
        # Check GRZ
        occupied_pixels = np.sum(heightmap > 0)
        expected_grz = occupied_pixels * (pixel_size ** 2) / buildable_area_m2
        print(f"  GRZ calculated: {features_planning[0]:.3f}, expected: {expected_grz:.3f} ✓" if abs(features_planning[0] - expected_grz) < 0.01 else f"  GRZ MISMATCH!")
        
        # Check GFZ
        total_floor_area = np.sum(heightmap) * (pixel_size ** 2)
        expected_gfz = total_floor_area / buildable_area_m2
        print(f"  GFZ calculated: {features_planning[1]:.3f}, expected: {expected_gfz:.3f} ✓" if abs(features_planning[1] - expected_gfz) < 0.01 else f"  GFZ MISMATCH!")
        
        # Check heights match between feature sets
        print(f"  Height consistency: Original={features_original[1]:.2f}m, Planning={features_planning[2]:.2f}m ✓" if abs(features_original[1] - features_planning[2]) < 0.01 else f"  HEIGHT MISMATCH!")
        
        # Check building count
        labeled_array, num_buildings = label(heightmap > 0)
        print(f"  Building count: Detected={num_buildings}, Original={int(features_original[3])}, Planning={int(features_planning[4])} ✓" if num_buildings == int(features_original[3]) == int(features_planning[4]) else f"  COUNT MISMATCH!")
        
        # Visualize
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        fig.suptitle(f'Test Case: {test_name}', fontsize=14, fontweight='bold')
        
        # Plot 1: Heightmap
        visualize_heightmap(axes[0], heightmap, 'Heightmap')
        
        # Plot 2: Building footprints
        footprint = (heightmap > 0).astype(int)
        axes[1].imshow(footprint, cmap='Greys', origin='lower', vmin=0, vmax=1)
        axes[1].set_title('Building Footprints', fontsize=10, fontweight='bold')
        axes[1].set_xlabel('X (pixels)', fontsize=8)
        axes[1].set_ylabel('Y (pixels)', fontsize=8)
        axes[1].grid(True, alpha=0.3, linewidth=0.5)
        
        # Add GRZ annotation
        axes[1].text(0.5, -0.15, f'GRZ = {features_planning[0]:.3f}', 
                    transform=axes[1].transAxes, ha='center', fontsize=10, 
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Plot 3: Feature comparison
        axes[2].axis('off')
        axes[2].set_title('Feature Values', fontsize=10, fontweight='bold')
        
        # Create text summary
        text_content = "ORIGINAL FEATURES:\n"
        for i, (name, value) in enumerate(zip(feature_names_orig, features_original)):
            text_content += f"  {name}: {value:.2f}\n"
        
        text_content += "\nPLANNING FEATURES:\n"
        for i, (name, value) in enumerate(zip(feature_names_planning, features_planning)):
            text_content += f"  {name}: {value:.2f}\n"
        
        axes[2].text(0.1, 0.95, text_content, transform=axes[2].transAxes,
                    fontsize=8, verticalalignment='top', fontfamily='monospace',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        
        # Save figure
        filename = f"{output_dir}/feature_test_{test_name.replace(' ', '_').lower()}.png"
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"\n  → Saved visualization to: {filename}")
        plt.close()
    
    print(f"\n{'='*80}")
    print("ALL TESTS COMPLETED")
    print(f"Visualizations saved to: {output_dir}/")
    print(f"{'='*80}\n")


def test_street_canyon_aspect_ratio():
    """Specific test for street canyon aspect ratio calculation."""
    print("\n" + "="*80)
    print("STREET CANYON ASPECT RATIO TEST")
    print("="*80)
    
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    
    # Create a perfect street canyon: 18m tall buildings, 30m apart
    heightmap = np.zeros((40, 40))
    heightmap[5:35, 5:10] = 18  # Left building
    heightmap[5:35, 30:35] = 18  # Right building
    # Distance between buildings: 20 pixels = 60m center-to-center
    # Width of street: (30-10) * 3 = 60m
    # Expected H/W = 18 / 60 = 0.3
    
    buildable_mask = np.ones_like(heightmap, dtype=bool)
    buildable_area_m2 = np.sum(buildable_mask) * (pixel_size ** 2)
    
    features = calculate_all_features_planning(heightmap, buildable_mask, buildable_area_m2)
    
    print(f"\nStreet Canyon Configuration:")
    print(f"  Building height: 18m")
    print(f"  Street width: 60m (20 pixels)")
    print(f"  Expected H/W: ~0.3")
    print(f"  Calculated H/W: {features[6]:.3f}")
    print(f"  Average distance: {features[5]:.1f}m")
    
    # Visualize
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle('Street Canyon Aspect Ratio Test', fontsize=14, fontweight='bold')
    
    visualize_heightmap(axes[0], heightmap, 'Street Canyon Layout')
    
    axes[1].axis('off')
    axes[1].set_title('Measurements', fontsize=10, fontweight='bold')
    text = f"""
    Configuration:
      Building Height (H): 18m
      Street Width (W): 60m
      Building Distance: {features[5]:.1f}m
      
    Aspect Ratio (H/W): {features[6]:.3f}
    
    Expected: ~0.3
    
    Status: {'✓ PASS' if abs(features[6] - 0.3) < 0.1 else '✗ FAIL'}
    """
    
    axes[1].text(0.1, 0.9, text, transform=axes[1].transAxes,
                fontsize=11, verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig('debug_plots/feature_test_street_canyon_aspect_ratio.png', dpi=150, bbox_inches='tight')
    print(f"\n  → Saved visualization to: debug_plots/feature_test_street_canyon_aspect_ratio.png")
    plt.close()
    
    print("="*80 + "\n")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("OPENSKIZZE FEATURE CALCULATION VISUAL TESTS")
    print("="*80)
    print("\nThis script tests both feature sets:")
    print("  1. Original features (built area, height, GFA, mass, etc.)")
    print("  2. Planning features (GRZ, GFZ, H/W ratio, SVF, etc.)")
    print("\nVisualizationswill be saved to debug_plots/")
    print("="*80)
    
    try:
        test_feature_calculations()
        test_street_canyon_aspect_ratio()
        print("\n✓ All tests completed successfully!")
        print("  Please review the visualizations in debug_plots/ for manual verification.\n")
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
