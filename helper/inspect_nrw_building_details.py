#!/usr/bin/env python3
"""
Deep inspection of NRW building data - check ALL attributes in detail
"""
import requests
import io
import geopandas
from shapely.geometry import box

def inspect_building_attributes_detailed():
    """Get detailed building data and inspect all attributes"""
    
    print("="*80)
    print("DETAILED INSPECTION OF NRW BUILDING DATA")
    print("="*80)
    
    # Current WFS endpoint we're using
    WFS_URL = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
    TYPE_NAME = "ave:GebaeudeBauwerk"
    
    # Small test area in Düsseldorf
    test_bbox = (6.77, 51.23, 6.772, 51.232)  # Very small area
    
    # Transform to EPSG:25832
    bbox_geom = box(test_bbox[0], test_bbox[1], test_bbox[2], test_bbox[3])
    gdf_bbox = geopandas.GeoDataFrame([1], geometry=[bbox_geom], crs="EPSG:4326")
    gdf_bbox_native = gdf_bbox.to_crs("EPSG:25832")
    min_x, min_y, max_x, max_y = gdf_bbox_native.total_bounds
    bbox_str = f"{min_x},{min_y},{max_x},{max_y},EPSG:25832"
    
    print(f"\nFetching buildings from test area...")
    print(f"BBOX: {bbox_str}")
    
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
        response = requests.get(WFS_URL, params=params, timeout=30)
        response.raise_for_status()
        
        # Save raw XML to inspect
        with open('nrw_buildings_sample.xml', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("✓ Saved raw XML to 'nrw_buildings_sample.xml'")
        
        # Parse with geopandas
        gdf = geopandas.read_file(io.BytesIO(response.content))
        
        if gdf.empty:
            print("❌ No buildings found")
            return
        
        print(f"\n✓ Fetched {len(gdf)} buildings")
        
        # Check ALL columns in detail
        print(f"\n{'='*80}")
        print("ALL AVAILABLE COLUMNS:")
        print(f"{'='*80}")
        
        for col in gdf.columns:
            if col == 'geometry':
                continue
                
            print(f"\n📋 Column: '{col}'")
            print(f"   Type: {gdf[col].dtype}")
            print(f"   Non-null: {gdf[col].notna().sum()} / {len(gdf)}")
            
            if gdf[col].notna().any():
                non_null = gdf[col].dropna()
                print(f"   Unique values: {non_null.nunique()}")
                
                # Show all unique values if reasonable number
                if non_null.nunique() < 20:
                    print(f"   All unique values: {sorted(non_null.unique())}")
                else:
                    print(f"   Sample values: {non_null.head(5).tolist()}")
                
                # Check if numeric
                if gdf[col].dtype in ['int64', 'float64']:
                    print(f"   Range: {non_null.min()} to {non_null.max()}")
                    print(f"   Mean: {non_null.mean():.2f}")
        
        # Try to get DescribeFeatureType to see schema
        print(f"\n\n{'='*80}")
        print("FETCHING SCHEMA INFORMATION (DescribeFeatureType)")
        print(f"{'='*80}")
        
        schema_params = {
            'service': 'WFS',
            'version': '1.1.0',
            'request': 'DescribeFeatureType',
            'typeName': TYPE_NAME
        }
        
        schema_response = requests.get(WFS_URL, params=schema_params, timeout=30)
        schema_response.raise_for_status()
        
        with open('nrw_buildings_schema.xml', 'w', encoding='utf-8') as f:
            f.write(schema_response.text)
        print("✓ Saved schema XML to 'nrw_buildings_schema.xml'")
        
        # Parse schema to find all possible attributes
        import xml.etree.ElementTree as ET
        schema_root = ET.fromstring(schema_response.content)
        
        # Look for element definitions
        namespaces = {
            'xs': 'http://www.w3.org/2001/XMLSchema',
            'xsd': 'http://www.w3.org/2001/XMLSchema'
        }
        
        print("\n📜 SCHEMA DEFINITION:")
        for elem in schema_root.findall('.//xs:element', namespaces):
            name = elem.get('name')
            elem_type = elem.get('type')
            if name and 'geom' not in name.lower():
                print(f"   - {name}: {elem_type}")
        
        # Also try XSD namespace
        for elem in schema_root.findall('.//xsd:element', namespaces):
            name = elem.get('name')
            elem_type = elem.get('type')
            if name and 'geom' not in name.lower():
                print(f"   - {name}: {elem_type}")
        
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE")
        print("="*80)
        print("\nFiles saved:")
        print("  - nrw_buildings_sample.xml (raw GML data)")
        print("  - nrw_buildings_schema.xml (feature type schema)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    inspect_building_attributes_detailed()
