#!/usr/bin/env python3
"""
Investigation script to find 3D building data from NRW open data portal
"""
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

# Known NRW WFS endpoints
WFS_ENDPOINTS = [
    "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht",
    "https://www.wfs.nrw.de/geobasis/wfs_nw_3d-gebaeudemodell_lod1",
    "https://www.wfs.nrw.de/geobasis/wfs_nw_3d-gebaeudemodell_lod2",
    "https://www.wfs.nrw.de/geobasis/wfs_nw_inspire-bu-3d",
]

def get_wfs_capabilities(wfs_url):
    """Fetch and parse WFS GetCapabilities to find available layers"""
    print(f"\n{'='*80}")
    print(f"Checking WFS: {wfs_url}")
    print(f"{'='*80}")
    
    params = {
        'service': 'WFS',
        'request': 'GetCapabilities',
        'version': '2.0.0'
    }
    
    try:
        response = requests.get(wfs_url, params=params, timeout=30)
        response.raise_for_status()
        
        # Parse XML
        root = ET.fromstring(response.content)
        
        # Define namespaces
        namespaces = {
            'wfs': 'http://www.opengis.net/wfs/2.0',
            'wfs1': 'http://www.opengis.net/wfs',
            'ows': 'http://www.opengis.net/ows/1.1',
        }
        
        # Try to find FeatureTypeList
        feature_types = []
        
        # Try WFS 2.0 namespace
        for ft in root.findall('.//wfs:FeatureType', namespaces):
            name_elem = ft.find('wfs:Name', namespaces)
            title_elem = ft.find('wfs:Title', namespaces)
            abstract_elem = ft.find('wfs:Abstract', namespaces)
            
            if name_elem is not None:
                feature_types.append({
                    'name': name_elem.text,
                    'title': title_elem.text if title_elem is not None else '',
                    'abstract': abstract_elem.text if abstract_elem is not None else ''
                })
        
        # Try WFS 1.1 namespace if no results
        if not feature_types:
            for ft in root.findall('.//wfs1:FeatureType', namespaces):
                name_elem = ft.find('wfs1:Name', namespaces)
                title_elem = ft.find('wfs1:Title', namespaces)
                abstract_elem = ft.find('wfs1:Abstract', namespaces)
                
                if name_elem is not None:
                    feature_types.append({
                        'name': name_elem.text,
                        'title': title_elem.text if title_elem is not None else '',
                        'abstract': abstract_elem.text if abstract_elem is not None else ''
                    })
        
        # If still no results, try without namespace
        if not feature_types:
            for ft in root.findall('.//FeatureType'):
                name_elem = ft.find('Name')
                title_elem = ft.find('Title')
                abstract_elem = ft.find('Abstract')
                
                if name_elem is not None:
                    feature_types.append({
                        'name': name_elem.text,
                        'title': title_elem.text if title_elem is not None else '',
                        'abstract': abstract_elem.text if abstract_elem is not None else ''
                    })
        
        if feature_types:
            print(f"\n✓ Found {len(feature_types)} feature type(s):")
            for i, ft in enumerate(feature_types, 1):
                print(f"\n  {i}. {ft['name']}")
                if ft['title']:
                    print(f"     Title: {ft['title']}")
                if ft['abstract']:
                    print(f"     Description: {ft['abstract'][:200]}...")
                    
                # Check if it mentions height/3D
                name_lower = ft['name'].lower()
                title_lower = ft['title'].lower()
                abstract_lower = ft['abstract'].lower()
                
                keywords = ['3d', 'lod', 'höhe', 'hoehe', 'height', 'geschoss', 'floor', 'storey']
                if any(kw in name_lower or kw in title_lower or kw in abstract_lower for kw in keywords):
                    print(f"     ⭐ POTENTIAL 3D/HEIGHT DATA!")
                    
            return feature_types
        else:
            print("❌ No feature types found in GetCapabilities response")
            print("\nFirst 500 chars of response:")
            print(response.text[:500])
            return []
            
    except requests.exceptions.Timeout:
        print("⏱ Timeout - service may not be available")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return []
    except ET.ParseError as e:
        print(f"❌ XML Parse Error: {e}")
        print("\nFirst 500 chars of response:")
        print(response.text[:500])
        return []

def test_feature_type(wfs_url, feature_type_name):
    """Fetch a sample feature to see what attributes are available"""
    print(f"\n{'='*80}")
    print(f"Testing feature type: {feature_type_name}")
    print(f"{'='*80}")
    
    # Düsseldorf area test bbox
    test_bbox = (6.76, 51.22, 6.78, 51.24)
    
    # Convert to EPSG:25832 for NRW services
    import geopandas
    from shapely.geometry import box
    bbox_geom = box(test_bbox[0], test_bbox[1], test_bbox[2], test_bbox[3])
    gdf_bbox = geopandas.GeoDataFrame([1], geometry=[bbox_geom], crs="EPSG:4326")
    gdf_bbox_native = gdf_bbox.to_crs("EPSG:25832")
    min_x, min_y, max_x, max_y = gdf_bbox_native.total_bounds
    bbox_str = f"{min_x},{min_y},{max_x},{max_y},EPSG:25832"
    
    params = {
        'service': 'WFS',
        'version': '2.0.0',
        'request': 'GetFeature',
        'typeName': feature_type_name,
        'count': '1',  # Just get 1 feature
        'BBOX': bbox_str,
        'outputFormat': 'application/gml+xml; version=3.2'
    }
    
    try:
        response = requests.get(wfs_url, params=params, timeout=30)
        response.raise_for_status()
        
        # Try to parse with geopandas
        import io
        try:
            gdf = geopandas.read_file(io.BytesIO(response.content))
            if not gdf.empty:
                print(f"\n✓ Successfully fetched {len(gdf)} feature(s)")
                print(f"\nAvailable columns:")
                for col in gdf.columns:
                    if col != 'geometry':
                        print(f"  - {col}: {gdf[col].dtype}")
                        if gdf[col].notna().any():
                            print(f"    Sample value: {gdf[col].iloc[0]}")
                
                # Check for height-related fields
                height_cols = [col for col in gdf.columns 
                              if any(kw in col.lower() 
                                    for kw in ['hoehe', 'height', 'geschoss', 'floor', 'lod', 'z', 'elevation'])]
                if height_cols:
                    print(f"\n⭐ HEIGHT-RELATED COLUMNS FOUND: {height_cols}")
                    for col in height_cols:
                        print(f"\n  Column: {col}")
                        print(f"  Type: {gdf[col].dtype}")
                        if gdf[col].notna().any():
                            print(f"  Value: {gdf[col].iloc[0]}")
                
                return True
            else:
                print("❌ No features returned for this bbox")
                return False
        except Exception as e:
            print(f"❌ Could not parse as GeoDataFrame: {e}")
            print("\nFirst 1000 chars of response:")
            print(response.text[:1000])
            return False
            
    except requests.exceptions.Timeout:
        print("⏱ Timeout")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "="*80)
    print("NRW Open Data Portal - 3D Building Data Investigation")
    print("="*80)
    
    all_feature_types = {}
    
    # Check all known WFS endpoints
    for wfs_url in WFS_ENDPOINTS:
        feature_types = get_wfs_capabilities(wfs_url)
        if feature_types:
            all_feature_types[wfs_url] = feature_types
    
    # Now test promising feature types
    print("\n\n" + "="*80)
    print("TESTING PROMISING FEATURE TYPES")
    print("="*80)
    
    for wfs_url, feature_types in all_feature_types.items():
        for ft in feature_types:
            # Look for 3D/height indicators in name
            name_lower = ft['name'].lower()
            if any(kw in name_lower for kw in ['3d', 'lod', 'hoehe', 'height']):
                test_feature_type(wfs_url, ft['name'])
    
    print("\n\n" + "="*80)
    print("INVESTIGATION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()
