#!/usr/bin/env python3
"""
Test script to verify if NRW open data portal provides building height information
"""
import sys
import numpy as np
from backend.data_io import fetch_existing_buildings_data

def test_nrw_building_heights():
    """Test if we can fetch and extract height data from NRW buildings"""
    
    print("=" * 80)
    print("Testing NRW Open Data Portal Building Height Data")
    print("=" * 80)
    
    # Test with a sample location in NRW (Düsseldorf area)
    # The function expects Web Mercator coordinates (lon, lat), not EPSG:25832
    # Using Düsseldorf city center area
    test_bbox = (6.76, 51.22, 6.78, 51.24)  # (min_lon, min_lat, max_lon, max_lat)
    
    print(f"\nFetching buildings from test area:")
    print(f"  Lon: {test_bbox[0]} - {test_bbox[2]}")
    print(f"  Lat: {test_bbox[1]} - {test_bbox[3]}")
    print()
    
    try:
        # Fetch building data
        gdf_buildings = fetch_existing_buildings_data(test_bbox)
        
        if gdf_buildings is None or gdf_buildings.empty:
            print("❌ ERROR: No buildings fetched from NRW portal")
            return False
        
        print(f"✓ Fetched {len(gdf_buildings)} buildings")
        print()
        
        # Check available columns
        print("Available columns in GeoDataFrame:")
        for col in gdf_buildings.columns:
            print(f"  - {col}")
        print()
        
        # Check for height-related columns
        height_columns = [col for col in gdf_buildings.columns 
                         if any(keyword in col.lower() 
                               for keyword in ['hoehe', 'height', 'geschoss', 'floor', 'storey', 'etage'])]
        
        if height_columns:
            print(f"✓ Found {len(height_columns)} height-related column(s): {height_columns}")
            print()
            
            for col in height_columns:
                print(f"Column: {col}")
                print(f"  Data type: {gdf_buildings[col].dtype}")
                print(f"  Non-null values: {gdf_buildings[col].notna().sum()} / {len(gdf_buildings)}")
                print(f"  Null values: {gdf_buildings[col].isna().sum()}")
                
                if gdf_buildings[col].notna().any():
                    non_null_values = gdf_buildings[col].dropna()
                    print(f"  Sample values: {non_null_values.head(10).tolist()}")
                    print(f"  Min: {non_null_values.min()}")
                    print(f"  Max: {non_null_values.max()}")
                    print(f"  Mean: {non_null_values.mean():.2f}")
                    print(f"  Median: {non_null_values.median():.2f}")
                else:
                    print(f"  ⚠ All values are null!")
                print()
        else:
            print("❌ WARNING: No height-related columns found in the data!")
            print("   This means the NRW portal does NOT provide height information.")
            print()
        
        # Check 'funktion' column (building function/type)
        if 'funktion' in gdf_buildings.columns:
            print("Building functions (types) available:")
            func_counts = gdf_buildings['funktion'].value_counts()
            for func, count in func_counts.items():
                print(f"  {func}: {count} buildings")
            print()
        
        # Test what happens with our current code
        print("Testing height extraction logic from optimization_process.py:")
        print("-" * 60)
        
        if 'hoehe' in gdf_buildings.columns:
            heights_meters = gdf_buildings['hoehe'].fillna(9.0)
            print(f"✓ Using 'hoehe' column (height in meters)")
            print(f"  Buildings with height data: {gdf_buildings['hoehe'].notna().sum()}")
            print(f"  Buildings using default (9.0m): {gdf_buildings['hoehe'].isna().sum()}")
        elif 'geschosszahl' in gdf_buildings.columns:
            heights_meters = gdf_buildings['geschosszahl'].fillna(3.0) * 3.0
            print(f"✓ Using 'geschosszahl' column (floors * 3m)")
            print(f"  Buildings with floor data: {gdf_buildings['geschosszahl'].notna().sum()}")
            print(f"  Buildings using default (3 floors = 9m): {gdf_buildings['geschosszahl'].isna().sum()}")
        else:
            print(f"❌ No height columns found - ALL buildings default to 9.0m")
            heights_meters = [9.0] * len(gdf_buildings)
        
        print()
        if isinstance(heights_meters, (list, np.ndarray)):
            heights_array = np.array(heights_meters)
        else:
            heights_array = heights_meters.values
            
        print(f"Final height statistics:")
        print(f"  Min height: {heights_array.min():.1f}m")
        print(f"  Max height: {heights_array.max():.1f}m")
        print(f"  Mean height: {heights_array.mean():.1f}m")
        print(f"  Median height: {np.median(heights_array):.1f}m")
        print(f"  Buildings with exactly 9.0m: {np.sum(heights_array == 9.0)}")
        print()
        
        # Verdict
        print("=" * 80)
        if height_columns and gdf_buildings[height_columns[0]].notna().any():
            non_null_count = gdf_buildings[height_columns[0]].notna().sum()
            percentage = (non_null_count / len(gdf_buildings)) * 100
            print(f"✓ SUCCESS: NRW provides height data for {percentage:.1f}% of buildings")
            print(f"           ({non_null_count} out of {len(gdf_buildings)} buildings)")
        else:
            print("❌ FAILURE: NRW does NOT provide usable height data")
            print("            All buildings will default to 9.0m height")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_nrw_building_heights()
    sys.exit(0 if success else 1)
