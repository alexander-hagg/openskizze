#!/usr/bin/env python3
"""
Test LOD2 tile integration in main application
"""
import sys
sys.path.insert(0, '/home/alex/Documents/_cloud/Funded_Projects/OpenSKIZZE/code/openskizze')

from backend.data_io import fetch_existing_buildings_data
from shapely.geometry import box
import geopandas

# Test with Paderborn University area (same as previous tests)
test_bbox_wgs84 = (8.67, 51.70, 8.69, 51.72)  # WGS84 (lon, lat)

print("=" * 80)
print("Testing LOD2 Integration in Main Application")
print("=" * 80)

print(f"\nTest Area (WGS84): {test_bbox_wgs84}")
print(f"  Lon: {test_bbox_wgs84[0]:.4f} to {test_bbox_wgs84[2]:.4f}")
print(f"  Lat: {test_bbox_wgs84[1]:.4f} to {test_bbox_wgs84[3]:.4f}")

print("\n" + "-" * 80)
print("Fetching buildings with fetch_existing_buildings_data()...")
print("-" * 80)

buildings = fetch_existing_buildings_data(test_bbox_wgs84)

if buildings is None or buildings.empty:
    print("\n❌ FAILED: No buildings returned")
    sys.exit(1)

print(f"\n✓ Success! Fetched {len(buildings)} buildings")
print(f"  CRS: {buildings.crs}")
print(f"  Columns: {list(buildings.columns)}")

# Check for measuredHeight column
if 'measuredHeight' in buildings.columns:
    heights = buildings['measuredHeight'].dropna()
    print(f"\n✓ Height data present:")
    print(f"  Buildings with heights: {len(heights)}/{len(buildings)} ({len(heights)/len(buildings)*100:.1f}%)")
    print(f"  Height range: {heights.min():.1f}m to {heights.max():.1f}m")
    print(f"  Mean height: {heights.mean():.1f}m")
    print(f"  Floors (÷3): {heights.min()/3:.1f} to {heights.max()/3:.1f} floors")
else:
    print("\n❌ WARNING: No measuredHeight column found!")

# Show sample buildings
print(f"\nSample buildings:")
for i, (idx, row) in enumerate(buildings.head(5).iterrows()):
    height = row.get('measuredHeight', None)
    if height:
        print(f"  {i+1}. Height: {height:.1f}m ({height/3:.1f} floors), Area: {row.geometry.area:.0f}m²")
    else:
        print(f"  {i+1}. No height data, Area: {row.geometry.area:.0f}m²")

print("\n" + "=" * 80)
print("✓ LOD2 Integration Test PASSED")
print("=" * 80)
