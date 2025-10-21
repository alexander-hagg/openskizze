#!/usr/bin/env python3
"""
Diagnostic script to check feature ranges for planning features.
Run this to see what actual feature values are being generated vs expected ranges.

Usage:
    python diagnose_feature_ranges.py [grid_width] [grid_length] [max_height] [min_distance]
    
Example:
    python diagnose_feature_ranges.py 50 40 25 5
    
Default: 34 34 30 0
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.encoding import ParametricEncoding
from backend.evaluation import calculate_all_features_planning
from backend.config import DOMAIN_CONFIG, ENCODING_CONFIG
from backend.optimization_process import _calculate_dynamic_feat_ranges

print("=" * 100)
print("FEATURE RANGE DIAGNOSTIC")
print("=" * 100)

# Parse command-line arguments or use defaults
if len(sys.argv) >= 5:
    grid_width = int(sys.argv[1])
    grid_length = int(sys.argv[2])
    max_height = float(sys.argv[3])
    min_distance = float(sys.argv[4])
    print(f"\n✓ Using command-line parameters:")
    print(f"  grid={grid_width}×{grid_length}, max_height={max_height}m, min_dist={min_distance}m")
elif len(sys.argv) >= 4:
    # Backwards compatibility: assume square if only 3 params
    grid_width = grid_length = int(sys.argv[1])
    max_height = float(sys.argv[2])
    min_distance = float(sys.argv[3])
    print(f"\n✓ Using command-line parameters (square):")
    print(f"  grid={grid_width}×{grid_length}, max_height={max_height}m, min_dist={min_distance}m")
else:
    # Simulate a typical parcel
    grid_width = grid_length = 34  # 34×34 grid (100m × 100m parcel)
    max_height = 30  # meters
    min_distance = 0  # meters
    print(f"\n⚠ Using default parameters (override with: python diagnose_feature_ranges.py [width] [length] [height] [distance])")

# Create buildable mask (simulate typical parcel - 70% buildable)
buildable_mask = np.ones((grid_length, grid_width), dtype=bool)
buildable_mask[:5, :] = False  # Remove some edges
buildable_mask[:, :5] = False

buildable_area_m2 = np.sum(buildable_mask) * (DOMAIN_CONFIG['pixel_size_in_meters'] ** 2)

print(f"\nTest Configuration:")
print(f"  Grid size: {grid_width}×{grid_length}")
print(f"  Parcel size: {grid_width * DOMAIN_CONFIG['pixel_size_in_meters']:.0f}m × {grid_length * DOMAIN_CONFIG['pixel_size_in_meters']:.0f}m")
print(f"  Buildable area: {buildable_area_m2:.0f} m²")
print(f"  Max height: {max_height} m")
print(f"  Min distance: {min_distance} m")

# Get calculated ranges for planning features
planning_ranges, _ = _calculate_dynamic_feat_ranges(
    buildable_mask, 
    max_height, 
    min_distance, 
    feature_set='planning'
)

print(f"\n{'='*100}")
print("CALCULATED FEATURE RANGES (Planning Features)")
print(f"{'='*100}")

feature_names = [
    "GRZ (Site Coverage)",
    "GFZ (Floor Area Ratio)",
    "Average Height (m)",
    "Height Variability (m)",
    "Number of Buildings",
    "Average Distance (m)",
    "H/W Aspect Ratio",
    "Sky View Factor"
]

for i, (name, range_vals) in enumerate(zip(feature_names, planning_ranges)):
    print(f"[{i}] {name:<30} Range: [{range_vals[0]:>8.2f}, {range_vals[1]:>8.2f}]  Span: {range_vals[1]-range_vals[0]:>8.2f}")

# Generate some test solutions and see what feature values they produce
print(f"\n{'='*100}")
print("ACTUAL FEATURE VALUES FROM RANDOM SOLUTIONS")
print(f"{'='*100}")

encoding_config = ENCODING_CONFIG.copy()
# Use the larger dimension for xy_length (encoding assumes square grid internally)
encoding_config['xy_length'] = max(grid_width, grid_length)
encoding_config['z_length'] = max_height
encoding = ParametricEncoding(encoding_config)

print(f"\nGenerating 100 random solutions and calculating their features...")

feature_samples = []
for _ in range(100):
    genome = np.random.randn(60)
    heightmap = encoding.express(buildable_mask, genome)
    
    # Skip empty solutions
    if np.sum(heightmap > 0) == 0:
        continue
    
    features = calculate_all_features_planning(heightmap, buildable_mask, buildable_area_m2)
    feature_samples.append(features)

if len(feature_samples) == 0:
    print("ERROR: No valid solutions generated!")
    sys.exit(1)

feature_samples = np.array(feature_samples)

print(f"\nGenerated {len(feature_samples)} valid solutions (out of 100 attempts)")
print(f"\n{'Feature':<30} {'Min':<10} {'Max':<10} {'Mean':<10} {'Expected Range':<25}")
print("-" * 100)

for i, name in enumerate(feature_names):
    min_val = np.min(feature_samples[:, i])
    max_val = np.max(feature_samples[:, i])
    mean_val = np.mean(feature_samples[:, i])
    expected = f"[{planning_ranges[i][0]:.2f}, {planning_ranges[i][1]:.2f}]"
    
    # Check if values are outside expected range
    warning = ""
    if min_val < planning_ranges[i][0] or max_val > planning_ranges[i][1]:
        warning = " ⚠ OUT OF RANGE!"
    
    # Check if values are very narrow (< 10% of expected range)
    actual_span = max_val - min_val
    expected_span = planning_ranges[i][1] - planning_ranges[i][0]
    if expected_span > 0 and actual_span < expected_span * 0.1:
        warning += " ⚠ NARROW DISTRIBUTION!"
    
    print(f"[{i}] {name:<25} {min_val:<10.4f} {max_val:<10.4f} {mean_val:<10.4f} {expected:<25} {warning}")

# Calculate what percentage of the feature space is being used
print(f"\n{'='*100}")
print("FEATURE SPACE COVERAGE ANALYSIS")
print(f"{'='*100}")

print(f"\nFor MAP-Elites grid discretization:")
num_bins = 5  # Typical QD configuration

for i, name in enumerate(feature_names):
    min_val = np.min(feature_samples[:, i])
    max_val = np.max(feature_samples[:, i])
    range_min, range_max = planning_ranges[i]
    
    if range_max > range_min:
        # Calculate which bins are being used
        # Normalize to 0-1 within the expected range
        normalized = (feature_samples[:, i] - range_min) / (range_max - range_min)
        normalized = np.clip(normalized, 0, 1)
        
        # Discretize into bins
        bin_indices = (normalized * (num_bins - 1e-6)).astype(int)
        unique_bins = len(np.unique(bin_indices))
        coverage_pct = (unique_bins / num_bins) * 100
        
        print(f"[{i}] {name:<30} Using {unique_bins}/{num_bins} bins ({coverage_pct:>5.1f}%)")
    else:
        print(f"[{i}] {name:<30} ZERO RANGE!")

# Estimate expected archive coverage for 2D feature space
print(f"\n{'='*100}")
print("EXPECTED ARCHIVE COVERAGE (2D Feature Space)")
print(f"{'='*100}")

print(f"\nWith {len(feature_samples)} solutions in 2D space ({num_bins}×{num_bins} = {num_bins**2} cells):")
print(f"  If features were uniformly distributed, we'd expect ~{len(feature_samples)} cells filled")
print(f"  Archive coverage would be ~{min(100, len(feature_samples) / (num_bins**2) * 100):.1f}%")

print(f"\n✓ Diagnostic complete!")
print(f"\nIf you see narrow distributions or features clustered in specific bins,")
print(f"this explains the low coverage (0.01% = ~1 cell filled out of 10,000).")
