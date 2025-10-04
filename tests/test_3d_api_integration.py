#!/usr/bin/env python3
"""
Quick test of the new 3D API integration
"""
import sys
sys.path.insert(0, '/home/alex/Documents/_cloud/Funded_Projects/OpenSKIZZE/code/openskizze')

from backend.data_io import fetch_existing_buildings_data

def test_integration():
    print("="*80)
    print("TESTING NRW 3D API INTEGRATION")
    print("="*80)
    
    # Test area in Düsseldorf
    test_bbox = (6.77, 51.23, 6.772, 51.232)
    
    print(f"\nTest area: {test_bbox}")
    print()
    
    # Fetch buildings
    gdf = fetch_existing_buildings_data(test_bbox)
    
    if gdf is None or gdf.empty:
        print("\n❌ No buildings fetched")
        return False
    
    print(f"\n✓ Fetched {len(gdf)} buildings")
    print(f"\nColumns: {list(gdf.columns)}")
    
    # Check for height data
    if 'measuredHeight' in gdf.columns:
        heights = gdf['measuredHeight'].dropna()
        print(f"\n✓ measuredHeight column exists!")
        print(f"  Buildings with height data: {len(heights)}/{len(gdf)}")
        if len(heights) > 0:
            print(f"  Min height: {heights.min():.2f}m")
            print(f"  Max height: {heights.max():.2f}m")
            print(f"  Mean height: {heights.mean():.2f}m")
            print(f"  Sample values: {heights.head(10).tolist()}")
            print("\n🎉 SUCCESS! Real building heights from LiDAR are available!")
            return True
        else:
            print("\n⚠ measuredHeight column exists but all values are null")
            return False
    else:
        print(f"\n❌ No measuredHeight column found")
        return False

if __name__ == "__main__":
    success = test_integration()
    sys.exit(0 if success else 1)
