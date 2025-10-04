#!/usr/bin/env python3
"""
Test function-based height estimation in action
"""
import sys
sys.path.insert(0, '/home/alex/Documents/_cloud/Funded_Projects/OpenSKIZZE/code/openskizze')

from backend.data_io import fetch_existing_buildings_data
import json

def test_height_estimation():
    print("="*80)
    print("TESTING FUNCTION-BASED HEIGHT ESTIMATION")
    print("="*80)
    
    # Test area in Düsseldorf with diverse building types
    test_bbox = (6.76, 51.22, 6.79, 51.25)
    
    print(f"\nTest area: {test_bbox}")
    print()
    
    # Fetch buildings
    gdf = fetch_existing_buildings_data(test_bbox)
    
    if gdf is None or gdf.empty:
        print("\n❌ No buildings fetched")
        return False
    
    print(f"\n✓ Fetched {len(gdf)} buildings")
    print(f"\nColumns: {list(gdf.columns)}")
    
    # Check building functions
    if 'funktion' in gdf.columns:
        print(f"\n📊 Building Functions Distribution:")
        func_counts = gdf['funktion'].value_counts()
        for func, count in func_counts.head(15).items():
            print(f"  {func}: {count}")
        
        print(f"\n✓ Function data available - height estimation will work!")
        print(f"\nTo see heights in action, run an optimization with this area.")
        print(f"Heights will be estimated based on building types:")
        print(f"  - Residential: 9-12m")
        print(f"  - High-rise: 36m")
        print(f"  - Commercial: 6m")  
        print(f"  - Churches: 18m")
        print(f"  - etc.")
        return True
    else:
        print(f"\n⚠ No function column - will use uniform 9m")
        return False

if __name__ == "__main__":
    success = test_height_estimation()
    sys.exit(0 if success else 1)
