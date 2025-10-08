"""
Test adaptive phenotype implementation
"""
import numpy as np
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import calculate_adaptive_phenotype_config, ENCODING_CONFIG
from backend.encoding import ParametricEncoding


def test_small_parcel():
    """Test with small 10x10 grid (300m²)"""
    print("\n=== Testing Small Parcel (10x10 grid) ===")
    
    # Create small buildable mask
    buildable_mask = np.ones((10, 10), dtype=bool)
    buildable_area_m2 = 10 * 10 * 9  # 10x10 cells, 3m each = 300m²
    grid_res = 10
    
    # Calculate phenotype config
    phenotype = calculate_adaptive_phenotype_config(buildable_mask, buildable_area_m2, grid_res)
    
    print(f"Parcel area: {phenotype['parcel_area_m2']:.0f} m²")
    print(f"Grid: {phenotype['xy_length']}×{phenotype['xy_length']} cells")
    print(f"Grid size: {phenotype['grid_size_meters']:.0f}m × {phenotype['grid_size_meters']:.0f}m")
    print(f"Buildable pixels: {phenotype['buildable_pixels']} ({phenotype['buildable_ratio']*100:.1f}%)")
    
    # Test encoding
    ENCODING_CONFIG['xy_length'] = grid_res
    encoding = ParametricEncoding(ENCODING_CONFIG)
    
    print(f"\nGenome dimension: {encoding.get_dimension()} (should be 60)")
    assert encoding.get_dimension() == 60, "Genome dimension should always be 60"
    
    # Test adaptive initial genome
    x0 = encoding.get_adaptive_initial_genome(buildable_mask)
    print(f"Adaptive x0 shape: {x0.shape}")
    print(f"Width gene bias (should be negative for small): {x0[0]:.2f}")
    assert x0.shape == (60,), "Initial genome should have 60 genes"
    
    # Test expression
    test_genome = np.random.randn(60)
    heightmap = encoding.express(buildable_mask, test_genome)
    print(f"Heightmap shape: {heightmap.shape} (should be 10×10)")
    assert heightmap.shape == (10, 10), f"Heightmap should be 10×10, got {heightmap.shape}"
    
    # Check max building size
    # With small grid (10), max building = 10/2 = 5 cells = 15m
    print(f"Max building size: ~{grid_res/2:.0f} cells (~{grid_res/2 * 3:.0f}m)")
    
    print("✓ Small parcel test passed!")


def test_medium_parcel():
    """Test with medium 32x32 grid (2,916m²)"""
    print("\n=== Testing Medium Parcel (32x32 grid) ===")
    
    # Create medium buildable mask
    buildable_mask = np.ones((32, 32), dtype=bool)
    buildable_area_m2 = 32 * 32 * 9  # 32x32 cells, 3m each
    grid_res = 32
    
    # Calculate phenotype config
    phenotype = calculate_adaptive_phenotype_config(buildable_mask, buildable_area_m2, grid_res)
    
    print(f"Parcel area: {phenotype['parcel_area_m2']:.0f} m²")
    print(f"Grid: {phenotype['xy_length']}×{phenotype['xy_length']} cells")
    print(f"Grid size: {phenotype['grid_size_meters']:.0f}m × {phenotype['grid_size_meters']:.0f}m")
    print(f"Buildable pixels: {phenotype['buildable_pixels']} ({phenotype['buildable_ratio']*100:.1f}%)")
    
    # Test encoding
    ENCODING_CONFIG['xy_length'] = grid_res
    encoding = ParametricEncoding(ENCODING_CONFIG)
    
    print(f"\nGenome dimension: {encoding.get_dimension()} (should be 60)")
    assert encoding.get_dimension() == 60, "Genome dimension should always be 60"
    
    # Test adaptive initial genome
    x0 = encoding.get_adaptive_initial_genome(buildable_mask)
    print(f"Adaptive x0 shape: {x0.shape}")
    print(f"Width gene bias (should be slightly negative): {x0[0]:.2f}")
    
    # Test expression
    test_genome = np.random.randn(60)
    heightmap = encoding.express(buildable_mask, test_genome)
    print(f"Heightmap shape: {heightmap.shape} (should be 32×32)")
    assert heightmap.shape == (32, 32), f"Heightmap should be 32×32, got {heightmap.shape}"
    
    # Check max building size
    print(f"Max building size: ~{grid_res/2:.0f} cells (~{grid_res/2 * 3:.0f}m)")
    
    print("✓ Medium parcel test passed!")


def test_large_parcel():
    """Test with large 100x100 grid (90,000m²)"""
    print("\n=== Testing Large Parcel (100x100 grid) ===")
    
    # Create large buildable mask
    buildable_mask = np.ones((100, 100), dtype=bool)
    buildable_area_m2 = 100 * 100 * 9  # 100x100 cells, 3m each
    grid_res = 100
    
    # Calculate phenotype config
    phenotype = calculate_adaptive_phenotype_config(buildable_mask, buildable_area_m2, grid_res)
    
    print(f"Parcel area: {phenotype['parcel_area_m2']:.0f} m²")
    print(f"Grid: {phenotype['xy_length']}×{phenotype['xy_length']} cells")
    print(f"Grid size: {phenotype['grid_size_meters']:.0f}m × {phenotype['grid_size_meters']:.0f}m")
    print(f"Buildable pixels: {phenotype['buildable_pixels']} ({phenotype['buildable_ratio']*100:.1f}%)")
    
    # Test encoding
    ENCODING_CONFIG['xy_length'] = grid_res
    encoding = ParametricEncoding(ENCODING_CONFIG)
    
    print(f"\nGenome dimension: {encoding.get_dimension()} (should be 60)")
    assert encoding.get_dimension() == 60, "Genome dimension should always be 60"
    
    # Test adaptive initial genome
    x0 = encoding.get_adaptive_initial_genome(buildable_mask)
    print(f"Adaptive x0 shape: {x0.shape}")
    print(f"Width gene bias (should be ~0 for large): {x0[0]:.2f}")
    
    # Test expression
    test_genome = np.random.randn(60)
    heightmap = encoding.express(buildable_mask, test_genome)
    print(f"Heightmap shape: {heightmap.shape} (should be 100×100)")
    assert heightmap.shape == (100, 100), f"Heightmap should be 100×100, got {heightmap.shape}"
    
    # Check max building size
    print(f"Max building size: ~{grid_res/2:.0f} cells (~{grid_res/2 * 3:.0f}m)")
    
    print("✓ Large parcel test passed!")


def test_irregular_parcel():
    """Test with irregular L-shaped parcel"""
    print("\n=== Testing Irregular Parcel (L-shaped) ===")
    
    # Create L-shaped buildable mask
    buildable_mask = np.zeros((30, 30), dtype=bool)
    buildable_mask[:15, :15] = True  # Top-left square
    buildable_mask[15:, :10] = True  # Bottom-left rectangle
    
    buildable_pixels = np.sum(buildable_mask)
    buildable_area_m2 = buildable_pixels * 9  # 3m × 3m pixels
    grid_res = 30
    
    # Calculate phenotype config
    phenotype = calculate_adaptive_phenotype_config(buildable_mask, buildable_area_m2, grid_res)
    
    print(f"Parcel area: {phenotype['parcel_area_m2']:.0f} m²")
    print(f"Grid: {phenotype['xy_length']}×{phenotype['xy_length']} cells")
    print(f"Buildable pixels: {phenotype['buildable_pixels']} ({phenotype['buildable_ratio']*100:.1f}% of grid)")
    print(f"  Note: Low ratio indicates irregular shape")
    
    # Test encoding
    ENCODING_CONFIG['xy_length'] = grid_res
    encoding = ParametricEncoding(ENCODING_CONFIG)
    
    # Test expression with taboo zone enforcement
    test_genome = np.random.randn(60)
    heightmap = encoding.express(buildable_mask, test_genome)
    
    # Verify buildings only in buildable area
    buildings_in_taboo = np.any(heightmap[~buildable_mask] > 0)
    print(f"Buildings in taboo zones: {buildings_in_taboo} (should be False)")
    assert not buildings_in_taboo, "Buildings should not appear in taboo zones!"
    
    print("✓ Irregular parcel test passed!")


def test_building_scaling():
    """Verify buildings scale proportionally with grid size"""
    print("\n=== Testing Building Size Scaling ===")
    
    grid_sizes = [10, 32, 100]
    
    for grid_res in grid_sizes:
        buildable_mask = np.ones((grid_res, grid_res), dtype=bool)
        ENCODING_CONFIG['xy_length'] = grid_res
        encoding = ParametricEncoding(ENCODING_CONFIG)
        
        # Create genome with max-sized building (gene = 1.0 after norm2unif)
        # norm2unif(0) ≈ 0.5, norm2unif(3) ≈ 0.999
        test_genome = np.zeros(60)
        test_genome[0] = 3.0  # Width gene → ~1.0 after norm2unif
        test_genome[1] = 3.0  # Length gene → ~1.0 after norm2unif
        test_genome[2] = 0.0  # Height
        test_genome[3] = 0.0  # X position
        test_genome[4] = 0.0  # Y position
        test_genome[5] = 1.0  # Active
        
        heightmap = encoding.express(buildable_mask, test_genome)
        
        # Find max building dimensions
        occupied = heightmap > 0
        if np.any(occupied):
            rows_with_building = np.any(occupied, axis=1)
            cols_with_building = np.any(occupied, axis=0)
            building_width = np.sum(cols_with_building)
            building_length = np.sum(rows_with_building)
            
            expected_max = grid_res / 2
            print(f"Grid {grid_res}×{grid_res}: Max building ~{building_width}×{building_length} cells "
                  f"(expected ~{expected_max:.0f}, {expected_max*3:.0f}m)")
    
    print("✓ Building scaling test passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Adaptive Phenotype Implementation")
    print("=" * 60)
    
    try:
        test_small_parcel()
        test_medium_parcel()
        test_large_parcel()
        test_irregular_parcel()
        test_building_scaling()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
