#!/usr/bin/env python3
"""
Search for buildings with anzahlgs (number of floors) data across larger area
"""
import requests
import io
import geopandas
from shapely.geometry import box
import time

def search_for_anzahlgs_data():
    """Search across multiple areas to find buildings with floor data"""
    
    print("="*80)
    print("SEARCHING FOR BUILDINGS WITH FLOOR DATA (anzahlgs)")
    print("="*80)
    
    WFS_URL = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
    TYPE_NAME = "ave:GebaeudeBauwerk"
    
    # Test multiple cities in NRW
    test_locations = [
        ("Düsseldorf", (6.76, 51.22, 6.79, 51.25)),
        ("Köln", (6.95, 50.93, 6.98, 50.96)),
        ("Dortmund", (7.46, 51.51, 7.49, 51.54)),
        ("Essen", (7.01, 51.45, 7.04, 51.48)),
        ("Bonn", (7.09, 50.73, 7.12, 50.76)),
    ]
    
    total_buildings = 0
    total_with_anzahlgs = 0
    
    for city, bbox in test_locations:
        print(f"\n{'='*60}")
        print(f"Testing: {city}")
        print(f"{'='*60}")
        
        # Transform to EPSG:25832
        bbox_geom = box(bbox[0], bbox[1], bbox[2], bbox[3])
        gdf_bbox = geopandas.GeoDataFrame([1], geometry=[bbox_geom], crs="EPSG:4326")
        gdf_bbox_native = gdf_bbox.to_crs("EPSG:25832")
        min_x, min_y, max_x, max_y = gdf_bbox_native.total_bounds
        bbox_str = f"{min_x},{min_y},{max_x},{max_y},EPSG:25832"
        
        params = {
            'service': 'WFS',
            'version': '1.1.0',
            'request': 'GetFeature',
            'typeName': TYPE_NAME,
            'outputFormat': 'text/xml; subtype=gml/3.2.1',
            'srsName': 'EPSG:25832',
            'BBOX': bbox_str
        }
        
        try:
            response = requests.get(WFS_URL, params=params, timeout=45)
            response.raise_for_status()
            
            gdf = geopandas.read_file(io.BytesIO(response.content))
            
            if gdf.empty:
                print(f"  No buildings found")
                continue
            
            total_buildings += len(gdf)
            
            # Check if anzahlgs column exists and has data
            if 'anzahlgs' in gdf.columns:
                with_floors = gdf['anzahlgs'].notna().sum()
                total_with_anzahlgs += with_floors
                
                print(f"  ✓ Found {len(gdf)} buildings")
                print(f"  ✓ anzahlgs column EXISTS!")
                print(f"  Buildings with floor data: {with_floors} ({with_floors/len(gdf)*100:.1f}%)")
                
                if with_floors > 0:
                    floor_data = gdf['anzahlgs'].dropna()
                    print(f"  Floor statistics:")
                    print(f"    Min: {floor_data.min()}")
                    print(f"    Max: {floor_data.max()}")
                    print(f"    Mean: {floor_data.mean():.1f}")
                    print(f"    Median: {floor_data.median():.1f}")
                    print(f"  Sample floor counts: {floor_data.head(10).tolist()}")
                    
                    # Show some examples
                    examples = gdf[gdf['anzahlgs'].notna()][['funktion', 'anzahlgs', 'gebnutzbez']].head(10)
                    print(f"\n  Examples with floor data:")
                    for idx, row in examples.iterrows():
                        print(f"    {row['funktion']}: {row['anzahlgs']} floors ({row['gebnutzbez']})")
                else:
                    print(f"  ❌ anzahlgs column exists but all values are null")
            else:
                print(f"  ✓ Found {len(gdf)} buildings")
                print(f"  ❌ No 'anzahlgs' column in data")
                print(f"  Available columns: {list(gdf.columns)}")
            
            time.sleep(1)  # Be nice to the server
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total buildings fetched: {total_buildings}")
    print(f"Buildings with floor data (anzahlgs): {total_with_anzahlgs}")
    if total_buildings > 0:
        print(f"Percentage with floor data: {total_with_anzahlgs/total_buildings*100:.2f}%")
    
    if total_with_anzahlgs == 0:
        print("\n❌ CONCLUSION: The 'anzahlgs' field is defined in the schema")
        print("   but does NOT contain actual data in the NRW ALKIS-vereinfacht dataset.")
        print("   All buildings will need to use estimated or default heights.")
    else:
        print(f"\n✓ CONCLUSION: Floor data IS available for some buildings!")
        print(f"   We can use this data where available and fall back to defaults.")

if __name__ == "__main__":
    search_for_anzahlgs_data()
