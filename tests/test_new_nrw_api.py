#!/usr/bin/env python3
"""
Test script to fetch 3D building data from the new NRW OGC API with LOD2 models
"""
import requests
import geopandas as gpd
from shapely.geometry import box
import json

def test_new_nrw_3d_api():
    """Test the new NRW OGC API for 3D building data with heights"""
    
    print("="*80)
    print("TESTING NEW NRW OGC API - LOD2 3D BUILDING DATA")
    print("="*80)
    
    # New API endpoint
    API_BASE = "https://ogc-api.nrw.de/3dg/v1"
    COLLECTION = "building"
    
    # Test area in Düsseldorf (slightly larger area)
    test_bbox_wgs84 = (6.76, 51.22, 6.79, 51.25)  # (min_lon, min_lat, max_lon, max_lat)
    
    print(f"\nTest Area (WGS84):")
    print(f"  Lon: {test_bbox_wgs84[0]} - {test_bbox_wgs84[2]}")
    print(f"  Lat: {test_bbox_wgs84[1]} - {test_bbox_wgs84[3]}")
    
    # Convert to EPSG:25832 (NRW native CRS)
    bbox_geom = box(*test_bbox_wgs84)
    gdf_bbox = gpd.GeoDataFrame([1], geometry=[bbox_geom], crs="EPSG:4326")
    gdf_bbox_native = gdf_bbox.to_crs("EPSG:25832")
    min_x, min_y, max_x, max_y = gdf_bbox_native.total_bounds
    
    print(f"\nTest Area (EPSG:25832):")
    print(f"  X: {min_x:.2f} - {max_x:.2f}")
    print(f"  Y: {min_y:.2f} - {max_y:.2f}")
    
    # Construct API request
    # OGC API Features uses bbox parameter: minx,miny,maxx,maxy
    # Try with WGS84 coordinates (default CRS for OGC API)
    url = f"{API_BASE}/collections/{COLLECTION}/items"
    
    # Try just getting a few items first without bbox to test the API
    params = {
        'limit': 10
    }
    
    print(f"\n📡 Fetching from API...")
    print(f"URL: {url}")
    print(f"Parameters: {params}")
    print()
    
    try:
        response = requests.get(url, params=params, timeout=60)
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}: {response.reason}")
            print(f"Response body: {response.text[:500]}")
        
        response.raise_for_status()
        
        data = response.json()
        
        if 'features' not in data:
            print("❌ No 'features' field in response")
            print(f"Response keys: {data.keys()}")
            return False
        
        features = data['features']
        print(f"✓ Received {len(features)} buildings")
        
        if len(features) == 0:
            print("⚠ No buildings found in this area")
            return False
        
        print(f"\n{'='*80}")
        print("ANALYZING BUILDING PROPERTIES")
        print(f"{'='*80}")
        
        # Check first building in detail
        first_building = features[0]
        props = first_building.get('properties', {})
        
        print(f"\nFirst building properties:")
        for key, value in props.items():
            if value is not None and key != 'geometry':
                print(f"  {key}: {value}")
        
        # Extract height data from all buildings
        heights = []
        floors = []
        
        for feature in features:
            props = feature.get('properties', {})
            
            if 'measuredHeight' in props and props['measuredHeight'] is not None:
                heights.append(props['measuredHeight'])
            
            if 'storeysAboveGround' in props and props['storeysAboveGround'] is not None:
                floors.append(props['storeysAboveGround'])
        
        print(f"\n{'='*80}")
        print("HEIGHT DATA ANALYSIS")
        print(f"{'='*80}")
        
        print(f"\nmeasuredHeight (Gebäudehöhe in Metern):")
        print(f"  Buildings with data: {len(heights)} / {len(features)} ({len(heights)/len(features)*100:.1f}%)")
        if heights:
            import numpy as np
            print(f"  Min: {np.min(heights):.2f} m")
            print(f"  Max: {np.max(heights):.2f} m")
            print(f"  Mean: {np.mean(heights):.2f} m")
            print(f"  Median: {np.median(heights):.2f} m")
            print(f"  Sample values: {heights[:10]}")
        else:
            print(f"  ❌ NO HEIGHT DATA!")
        
        print(f"\nstoreysAboveGround (Geschosse):")
        print(f"  Buildings with data: {len(floors)} / {len(features)} ({len(floors)/len(features)*100:.1f}%)")
        if floors:
            import numpy as np
            print(f"  Min: {np.min(floors)}")
            print(f"  Max: {np.max(floors)}")
            print(f"  Mean: {np.mean(floors):.1f}")
            print(f"  Median: {np.median(floors):.1f}")
            print(f"  Sample values: {floors[:10]}")
        else:
            print(f"  ❌ NO FLOOR DATA!")
        
        # Try to load as GeoDataFrame
        print(f"\n{'='*80}")
        print("CONVERTING TO GEODATAFRAME")
        print(f"{'='*80}")
        
        gdf = gpd.GeoDataFrame.from_features(data['features'], crs="EPSG:25832")
        print(f"\n✓ Successfully created GeoDataFrame")
        print(f"  Shape: {gdf.shape}")
        print(f"  Columns: {list(gdf.columns)}")
        
        # Check which columns have data
        print(f"\nColumn data availability:")
        for col in gdf.columns:
            if col != 'geometry':
                non_null = gdf[col].notna().sum()
                print(f"  {col}: {non_null}/{len(gdf)} ({non_null/len(gdf)*100:.1f}%)")
        
        print(f"\n{'='*80}")
        print("VERDICT")
        print(f"{'='*80}")
        
        if len(heights) > 0:
            print(f"✓ SUCCESS! The new NRW OGC API provides REAL building heights!")
            print(f"           {len(heights)} out of {len(features)} buildings have measuredHeight data")
            print(f"           ({len(heights)/len(features)*100:.1f}% coverage)")
            return True
        else:
            print(f"❌ FAILURE: No height data in response")
            return False
        
    except requests.exceptions.Timeout:
        print("❌ Request timeout")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    success = test_new_nrw_3d_api()
    sys.exit(0 if success else 1)
