#!/usr/bin/env python3
"""
Performance comparison test between old WFS API and new OGC 3D API.

This script tests several hypotheses for why the new API is slower:
1. Response size (CityGML vs simple GML)
2. Network latency/server performance
3. Parsing complexity (XML parsing time)
4. Pagination behavior
"""

import requests
import time
import geopandas
import io
import json
import xml.etree.ElementTree as ET
from shapely.geometry import box, Polygon

# Test area: Small bbox in Bonn city center (should have ~5-10 buildings)
# These coordinates represent THE EXACT SAME geographic area
TEST_BBOX_WGS84 = (7.0950, 50.7340, 7.0980, 50.7360)  # lon_min, lat_min, lon_max, lat_max (WGS84/EPSG:4326)
TEST_BBOX_EPSG25832 = (365569.0, 5621975.9, 365786.4, 5622192.8)  # x_min, y_min, x_max, y_max (EPSG:25832/UTM32N)
# Converted using pyproj Transformer.from_crs('EPSG:4326', 'EPSG:25832')

# API endpoints
WFS_URL = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
OGC_API_URL = "https://ogc-api.nrw.de/3dg/v1"

def test_old_wfs_api():
    """Test the old WFS API performance."""
    print("\n" + "="*80)
    print("TEST 1: OLD WFS API")
    print("="*80)
    
    min_x, min_y, max_x, max_y = TEST_BBOX_EPSG25832
    bbox_str = f"{min_x},{min_y},{max_x},{max_y},EPSG:25832"
    
    params = {
        'service': 'WFS',
        'version': '1.1.0',
        'request': 'GetFeature',
        'typeName': 'ave:GebaeudeBauwerk',
        'outputFormat': 'text/xml; subtype=gml/3.2.1',
        'srsName': 'EPSG:25832',
        'BBOX': bbox_str
    }
    
    print(f"Request URL: {WFS_URL}")
    print(f"Params: {params}")
    print(f"BBOX: {bbox_str}")
    
    # Time the request
    start_time = time.time()
    response = requests.get(WFS_URL, params=params, timeout=60)
    request_time = time.time() - start_time
    
    print(f"\n✓ Request completed in {request_time:.2f} seconds")
    print(f"  Status code: {response.status_code}")
    print(f"  Response size: {len(response.content):,} bytes ({len(response.content)/1024:.1f} KB)")
    
    # Time the parsing
    start_time = time.time()
    gml_content = io.BytesIO(response.content)
    gdf = geopandas.read_file(gml_content)
    parse_time = time.time() - start_time
    
    print(f"✓ Parsing completed in {parse_time:.2f} seconds")
    print(f"  Buildings found: {len(gdf)}")
    
    if len(gdf) > 0:
        print(f"  Columns: {list(gdf.columns)}")
        if 'funktion' in gdf.columns:
            print(f"  Functions: {gdf['funktion'].value_counts().to_dict()}")
    
    print(f"\n📊 TOTAL TIME: {request_time + parse_time:.2f} seconds")
    
    return {
        'request_time': request_time,
        'parse_time': parse_time,
        'total_time': request_time + parse_time,
        'response_size': len(response.content),
        'building_count': len(gdf)
    }


def test_new_ogc_api():
    """Test the new OGC 3D Geobasisdaten API with CityGML format."""
    print("\n" + "="*80)
    print("TEST 2: New OGC 3D API (CityGML format, FULL GEOMETRY)")
    print("="*80)
    
    base_url = "https://ogc-api.nrw.de/3dg/v1/collections/building/items"
    
    # Use WGS84 coordinates for OGC API
    lon_min, lat_min, lon_max, lat_max = TEST_BBOX_WGS84
    
    params = {
        'bbox': f'{lon_min},{lat_min},{lon_max},{lat_max}',
        'f': 'citygml',
        'limit': 1000
    }
    
    print(f"\nFetching from: {base_url}")
    print(f"Parameters: {params}")
    
    start_time = time.time()
    
    try:
        response = requests.get(base_url, params=params, timeout=120)
        
        fetch_time = time.time() - start_time
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Size: {len(response.content):,} bytes ({len(response.content)/1024:.1f} KB)")
        print(f"Fetch Time: {fetch_time:.2f} seconds")
        
        if response.status_code == 200:
            # Parse CityGML to extract buildings
            parse_start = time.time()
            buildings = parse_citygml_simple(response.content)
            parse_time = time.time() - parse_start
            
            print(f"Parse Time: {parse_time:.3f} seconds")
            print(f"Buildings Found: {len(buildings)}")
            
            if buildings:
                print("\nSample building data:")
                for i, building in enumerate(buildings[:3]):
                    print(f"  Building {i+1}:")
                    print(f"    ID: {building.get('id', 'N/A')}")
                    print(f"    Height: {building.get('measuredHeight', 'N/A')} m")
            
            print(f"\nTotal Time: {fetch_time + parse_time:.2f} seconds")
            print(f"  - Network: {fetch_time:.2f}s ({fetch_time/(fetch_time+parse_time)*100:.1f}%)")
            print(f"  - Parsing: {parse_time:.2f}s ({parse_time/(fetch_time+parse_time)*100:.1f}%)")
            
            return {
                'success': True,
                'buildings_count': len(buildings),
                'fetch_time': fetch_time,
                'parse_time': parse_time,
                'total_time': fetch_time + parse_time,
                'response_size': len(response.content)
            }
        else:
            print(f"Error: {response.text[:500]}")
            return {'success': False, 'error': response.status_code}
            
    except Exception as e:
        print(f"Exception: {str(e)}")
        return {'success': False, 'error': str(e)}


def test_ogc_api_json_format():
    """Test the OGC API using GeoJSON format (should be lighter than CityGML)."""
    print("\n" + "="*80)
    print("TEST 3: New OGC 3D API (GeoJSON format)")
    print("="*80)
    
    base_url = "https://ogc-api.nrw.de/3dg/v1/collections/building/items"
    
    # Use WGS84 coordinates for OGC API
    lon_min, lat_min, lon_max, lat_max = TEST_BBOX_WGS84
    
    # Request GeoJSON format (don't use 'f' parameter, let Accept header handle it)
    params = {
        'bbox': f'{lon_min},{lat_min},{lon_max},{lat_max}',
        'limit': 1000
    }
    
    headers = {
        'Accept': 'application/geo+json'
    }
    
    print(f"\nFetching from: {base_url}")
    print(f"Parameters: {params}")
    print(f"Headers: {headers}")
    print(f"Strategy: Use GeoJSON (via Accept header) instead of CityGML")
    
    start_time = time.time()
    
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=120)
        
        fetch_time = time.time() - start_time
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"Response Size: {len(response.content):,} bytes ({len(response.content)/1024:.1f} KB, {len(response.content)/1024/1024:.2f} MB)")
        print(f"Fetch Time: {fetch_time:.2f} seconds")
        
        if response.status_code == 200:
            # Parse JSON response
            parse_start = time.time()
            try:
                data = response.json()
                parse_time = time.time() - parse_start
                
                # Extract buildings from GeoJSON
                buildings = []
                if 'features' in data:
                    for feature in data['features']:
                        building = {
                            'id': feature.get('id', feature.get('properties', {}).get('gml_id', 'N/A')),
                            'measuredHeight': feature.get('properties', {}).get('measuredHeight', 'N/A')
                        }
                        buildings.append(building)
                
                print(f"Parse Time: {parse_time:.3f} seconds")
                print(f"Buildings Found: {len(buildings)}")
                
                if buildings:
                    print("\nSample building data:")
                    for i, building in enumerate(buildings[:5]):
                        print(f"  Building {i+1}:")
                        print(f"    ID: {building.get('id', 'N/A')}")
                        print(f"    Height: {building.get('measuredHeight', 'N/A')} m")
                
                print(f"\nTotal Time: {fetch_time + parse_time:.2f} seconds")
                print(f"  - Network: {fetch_time:.2f}s ({fetch_time/(fetch_time+parse_time)*100:.1f}%)")
                print(f"  - Parsing: {parse_time:.2f}s ({parse_time/(fetch_time+parse_time)*100:.1f}%)")
                
                return {
                    'success': True,
                    'buildings_count': len(buildings),
                    'fetch_time': fetch_time,
                    'parse_time': parse_time,
                    'total_time': fetch_time + parse_time,
                    'response_size': len(response.content)
                }
            except json.JSONDecodeError as e:
                print(f"JSON Parse Error: {e}")
                print(f"Response preview: {response.text[:500]}")
                return {'success': False, 'error': 'JSON parse error'}
        else:
            print(f"Error: {response.text[:500]}")
            return {'success': False, 'error': response.status_code}
            
    except Exception as e:
        print(f"Exception: {str(e)}")
        return {'success': False, 'error': str(e)}


def parse_citygml_simple(xml_content: bytes):
    """
    Simplified CityGML parser for testing.
    """
    try:
        root = ET.fromstring(xml_content)
        
        ns = {
            'core': 'http://www.opengis.net/citygml/1.0',
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gml': 'http://www.opengis.net/gml',
        }
        
        buildings = []
        
        for building_elem in root.findall('.//bldg:Building', ns):
            try:
                gml_id = building_elem.get('{http://www.opengis.net/gml}id', '')
                
                height_elem = building_elem.find('.//bldg:measuredHeight', ns)
                measured_height = float(height_elem.text) if height_elem is not None else None
                
                ground_surface = building_elem.find('.//bldg:GroundSurface//gml:Polygon', ns)
                
                if ground_surface is not None:
                    pos_list = ground_surface.find('.//gml:posList', ns)
                    if pos_list is not None:
                        coords_text = pos_list.text.strip()
                        srs_dim = int(pos_list.get('srsDimension', '3'))
                        
                        coords = [float(x) for x in coords_text.split()]
                        
                        coord_tuples = []
                        for i in range(0, len(coords), srs_dim):
                            if srs_dim == 3:
                                lon, lat, h = coords[i:i+3]
                                coord_tuples.append((lon, lat))
                            elif srs_dim == 2:
                                lon, lat = coords[i:i+2]
                                coord_tuples.append((lon, lat))
                        
                        if len(coord_tuples) >= 3:
                            polygon = Polygon(coord_tuples)
                            
                            buildings.append({
                                'gml_id': gml_id,
                                'measuredHeight': measured_height,
                                'geometry': polygon
                            })
            except Exception as e:
                continue
        
        if buildings:
            gdf = geopandas.GeoDataFrame(buildings, crs="EPSG:4326")
            return gdf
        else:
            return None
            
    except Exception as e:
        print(f"  ✗ Parsing error: {e}")
        return None


def test_ogc_format(format_name, f_param):
    """Test OGC API with specific format."""
    print("\n" + "="*80)
    print(f"TEST: OGC API - Format: {format_name.upper()}")
    print("="*80)
    
    min_lon, min_lat, max_lon, max_lat = TEST_BBOX_WGS84
    
    url = f"{OGC_API_URL}/collections/building/items"
    params = {
        'bbox': f"{min_lon},{min_lat},{max_lon},{max_lat}",
        'limit': 1000,
        'f': f_param
    }
    
    print(f"Request URL: {url}")
    print(f"Format parameter: f={f_param}")
    print(f"BBOX (WGS84): {min_lon},{min_lat},{max_lon},{max_lat}")
    
    try:
        start_time = time.time()
        response = requests.get(url, params=params, timeout=60)
        request_time = time.time() - start_time
        
        print(f"\n✓ Request completed in {request_time:.2f} seconds")
        print(f"  Status code: {response.status_code}")
        print(f"  Response size: {len(response.content):,} bytes ({len(response.content)/1024:.1f} KB)")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        
        if response.status_code != 200:
            print(f"  ✗ Error: {response.text[:200]}")
            return None
        
        # Try to parse based on format
        start_time = time.time()
        building_count = 0
        
        if format_name == 'citygml':
            gdf = parse_citygml_simple(response.content)
            building_count = len(gdf) if gdf is not None else 0
            
        elif format_name in ['cityjson', 'json']:
            import json
            try:
                data = json.loads(response.content)
                if 'CityObjects' in data:
                    building_count = len(data['CityObjects'])
                elif 'features' in data:
                    building_count = len(data['features'])
                print(f"  Buildings in JSON: {building_count}")
            except:
                print(f"  Could not parse JSON")
                
        elif format_name == 'glb':
            print(f"  GLB is binary glTF - cannot count buildings")
            building_count = -1
            
        parse_time = time.time() - start_time
        print(f"✓ Processing completed in {parse_time:.2f} seconds")
        print(f"\n📊 TOTAL TIME: {request_time + parse_time:.2f} seconds")
        
        return {
            'format': format_name,
            'request_time': request_time,
            'parse_time': parse_time,
            'total_time': request_time + parse_time,
            'response_size': len(response.content),
            'building_count': building_count
        }
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def test_with_different_limits():
    """Test how pagination affects performance."""
    print("\n" + "="*80)
    print("TEST 4: DIFFERENT LIMIT VALUES")
    print("="*80)
    
    min_lon, min_lat, max_lon, max_lat = TEST_BBOX_WGS84
    url = f"{OGC_API_URL}/collections/building/items"
    
    limits = [10, 100, 1000]
    
    for limit in limits:
        print(f"\n--- Testing with limit={limit} ---")
        params = {
            'bbox': f"{min_lon},{min_lat},{max_lon},{max_lat}",
            'limit': limit
        }
        
        try:
            start_time = time.time()
            response = requests.get(url, params=params, timeout=60)
            request_time = time.time() - start_time
            
            print(f"  Request time: {request_time:.2f}s")
            print(f"  Response size: {len(response.content):,} bytes ({len(response.content)/1024:.1f} KB)")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")


def main():
    """Run all tests and compare results."""
    print("\n" + "#"*80)
    print("# NRW Building Data API Performance Comparison")
    print("# Test Area: Bonn City Center (small bbox)")
    print("#"*80)
    
    results = {}
    
    # Test old WFS API
    results['wfs'] = test_old_wfs_api()
    
    # Test new OGC API with GeoJSON format
    results['ogc_json'] = test_ogc_api_json_format()
    
    # Test new OGC API with full geometry in CityGML (original test)
    results['ogc_citygml'] = test_new_ogc_api()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if results['wfs']['success']:
        wfs_time = results['wfs']['total_time']
        wfs_size = results['wfs']['response_size']
        
        print(f"\nWFS API (2D footprints, no heights):")
        print(f"  Buildings: {results['wfs']['buildings_count']}")
        print(f"  Time: {wfs_time:.2f}s")
        print(f"  Size: {wfs_size:,} bytes ({wfs_size/1024:.1f} KB)")
    
    if results['ogc_json']['success']:
        ogc_json_time = results['ogc_json']['total_time']
        ogc_json_size = results['ogc_json']['response_size']
        
        print(f"\nOGC 3D API (GeoJSON format):")
        print(f"  Buildings: {results['ogc_json']['buildings_count']}")
        print(f"  Time: {ogc_json_time:.2f}s")
        print(f"  Size: {ogc_json_size:,} bytes ({ogc_json_size/1024:.1f} KB)")
        
        if results['wfs']['success']:
            print(f"  vs WFS: {ogc_json_time/wfs_time:.1f}x slower, {ogc_json_size/wfs_size:.1f}x larger")
    
    if results['ogc_citygml']['success']:
        ogc_citygml_time = results['ogc_citygml']['total_time']
        ogc_citygml_size = results['ogc_citygml']['response_size']
        
        print(f"\nOGC 3D API (CityGML format, LOD2 with full geometry):")
        print(f"  Buildings: {results['ogc_citygml']['buildings_count']}")
        print(f"  Time: {ogc_citygml_time:.2f}s")
        print(f"  Size: {ogc_citygml_size:,} bytes ({ogc_citygml_size/1024:.1f} KB)")
        
        if results['wfs']['success']:
            print(f"  vs WFS: {ogc_citygml_time/wfs_time:.1f}x slower, {ogc_citygml_size/wfs_size:.1f}x larger")
        
        if results['ogc_json']['success']:
            print(f"  vs GeoJSON: {ogc_citygml_time/ogc_json_time:.1f}x slower, {ogc_citygml_size/ogc_json_size:.1f}x larger")
    
    print(f"\n" + "-"*80)
    print(f"KEY FINDING:")
    if results['ogc_json']['success'] and results['ogc_citygml']['success']:
        speedup = ogc_citygml_time / ogc_json_time
        size_reduction = ogc_citygml_size / ogc_json_size
        print(f"  GeoJSON vs CityGML comparison:")
        print(f"    - GeoJSON is {speedup:.1f}x FASTER")
        print(f"    - GeoJSON is {size_reduction:.1f}x SMALLER")
        print(f"  Recommendation: Use GeoJSON format (f=json) instead of CityGML!")
    print("="*80)


if __name__ == "__main__":
    main()
