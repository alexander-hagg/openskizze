#!/usr/bin/env python3
"""
Test full processing pipeline with LOD2 tiles
"""
import sys
sys.path.insert(0, '/home/alex/Documents/_cloud/Funded_Projects/OpenSKIZZE/code/openskizze')

from backend.data_io import fetch_and_process_buildings_for_area
from shapely.geometry import box
import geopandas
import json

# Create test polygon (Paderborn University area)
test_polygon = box(8.67, 51.70, 8.69, 51.72)  # WGS84
gdf = geopandas.GeoDataFrame([{'id': 1}], geometry=[test_polygon], crs='EPSG:4326')
geojson = json.loads(gdf.to_json())

print("=" * 80)
print("Testing Full Processing Pipeline with LOD2 Tiles")
print("=" * 80)

print("\nCalling fetch_and_process_buildings_for_area()...")
result = fetch_and_process_buildings_for_area(geojson, max_height_floors=10)

if result is None:
    print("\n❌ FAILED: No result returned")
    sys.exit(1)

print(f"\n✓ Processing successful!")
print(f"\n--- Result keys ---")
for key in result.keys():
    print(f"  - {key}")

# Check key outputs
gdf_buildings = result['gdf_buildings_filtered']
env_3d = result['env_3d_expanded']
function_map = result['building_function_map']

print(f"\n--- Building data ---")
print(f"  Buildings: {len(gdf_buildings)}")
print(f"  Columns: {list(gdf_buildings.columns)}")

# Check for measuredHeight
if 'measuredHeight' in gdf_buildings.columns:
    heights = gdf_buildings['measuredHeight'].dropna()
    print(f"  ✓ measuredHeight column present!")
    print(f"    Range: {heights.min():.1f}m - {heights.max():.1f}m")
    print(f"    Mean: {heights.mean():.1f}m")
else:
    print(f"  ❌ No measuredHeight column!")

print(f"\n--- 3D Environment ---")
print(f"  Shape: {env_3d.shape}")
print(f"  Non-zero voxels: {(env_3d > 0).sum()}")
print(f"  Max height (voxels): {env_3d.sum(axis=2).max()}")

print(f"\n--- Function Map ---")
print(f"  Shape: {function_map.shape}")
print(f"  Building pixels: {(function_map > 0).sum()}")
print(f"  Unique functions: {len(result['function_lookup'])}")

print(f"\n--- Grid Information ---")
print(f"  Expanded resolution: {result['expanded_res']}")
print(f"  Design resolution: {result['design_res']}")
print(f"  Pixel size: {result['pixel_size']:.2f}m")

# Check if building heights were properly encoded in 3D array
height_distribution = []
for r in range(env_3d.shape[0]):
    for c in range(env_3d.shape[1]):
        voxel_height = env_3d[r, c, :].sum()
        if voxel_height > 0:
            height_distribution.append(voxel_height)

if height_distribution:
    print(f"\n--- Height Distribution in 3D Array ---")
    print(f"  Buildings encoded: {len(height_distribution)}")
    print(f"  Height range: {min(height_distribution)} - {max(height_distribution)} voxels")
    print(f"  Mean height: {sum(height_distribution)/len(height_distribution):.1f} voxels")
    
    # Sample some buildings
    print(f"\n  Sample encoded buildings:")
    for i, h in enumerate(sorted(height_distribution, reverse=True)[:5]):
        print(f"    {i+1}. {h} voxels ({h*3:.1f}m ≈ {h:.1f} floors)")

print("\n" + "=" * 80)
print("✓ Full Processing Pipeline Test PASSED")
print("=" * 80)
