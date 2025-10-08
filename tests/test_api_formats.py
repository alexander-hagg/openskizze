#!/usr/bin/env python3
"""
Comprehensive API format testing.

Tests:
1. WFS API (corrected coordinates)
2. OGC API with different formats: citygml, cityjson, cityjsonseq, glb
3. Performance comparison
"""

import requests
import time
import geopandas as gpd
import io
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon

# Test area: Small bbox in Bonn city center
# WGS84 (lon, lat) coordinates
TEST_BBOX_WGS84 = (7.0950, 50.7340, 7.0980, 50.7360)

# EPSG:25832 coordinates (UTM zone 32N) - converted from WGS84
# Using proper coordinate transformation
TEST_BBOX_EPSG25832 = (356850, 5627600, 357050, 5627800)

# API endpoints
WFS_URL = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
OGC_API_URL = "https://ogc-api.nrw.de/3dg/v1"


def test_wfs_api_corrected():
    """Test WFS API with corrected coordinates."""
    print("\n" + "="*80)
    print("TEST 1: WFS API (Corrected Coordinates)")
    print("="*80)
    
    min_x, min_y, max_x, max_y = TEST_BBOX_EPSG25832
    bbox_str = f"{min_x},{min_y},{max_x},{max_y}"
    
    params = {
        'service': 'WFS',
        'version': '2.0.0',
        'request': 'GetFeature',
        'typeName': 'ave:GebaeudeBauwerk',
        'outputFormat': 'application/gml+xml; version=3.2',
        'srsName': 'EPSG:25832',
        'BBOX': bbox_str
    }
    
    print(f"Request URL: {WFS_URL}")
    print(f"BBOX (EPSG:25832): {bbox_str}")
    
    try:
        # Time the request
        start_time = time.time()
        response = requests.get(WFS_URL, params=params, timeout=60)
        request_time = time.time() - start_time
        
        print(f"\n✓ Request completed in {request_time:.2f} seconds")
        print(f"  Status code: {response.status_code}")
        print(f"  Response size: {len(response.content):,} bytes ({len(response.content)/1024:.1f} KB)")
        
        if response.status_code != 200:
            print(f"  ✗ Error response:")
            print(f"    {response.text[:500]}")
            return None
        
        # Time the parsing
        start_time = time.time()
        try:
            gml_content = io.BytesIO(response.content)
            gdf = gpd.read_file(gml_content)
            parse_time = time.time() - start_time
            
            print(f"✓ Parsing completed in {parse_time:.2f} seconds")
            print(f"  Buildings found: {len(gdf)}")
            
            if len(gdf) > 0:
                print(f"  Columns: {list(gdf.columns)[:10]}")  # First 10 columns
                if 'funktion' in gdf.columns:
                    print(f"  Functions: {gdf['funktion'].value_counts().head().to_dict()}")
        except Exception as e:
            parse_time = 0
            gdf = None
            print(f"  ✗ Parsing failed: {e}")
        
        print(f"\n📊 TOTAL TIME: {request_time + parse_time:.2f} seconds")
        
        return {
            'format': 'WFS GML',
            'request_time': request_time,
            'parse_time': parse_time,
            'total_time': request_time + parse_time,
            'response_size': len(response.content),
            'building_count': len(gdf) if gdf is not None else 0
        }
    except Exception as e:
        print(f"✗ Request failed: {e}")
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
        'f': f_param,
        'limit': 1000
    }
    
    print(f"Request URL: {url}")
    print(f"Format parameter: {f_param}")
    print(f"BBOX (WGS84): {min_lon},{min_lat},{max_lon},{max_lat}")
    
    try:
        # Time the request
        start_time = time.time()
        response = requests.get(url, params=params, timeout=60)
        request_time = time.time() - start_time
        
        print(f"\n✓ Request completed in {request_time:.2f} seconds")
        print(f"  Status code: {response.status_code}")
        print(f"  Response size: {len(response.content):,} bytes ({len(response.content)/1024:.1f} KB)")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        
        if response.status_code != 200:
            print(f"  ✗ Error response:")
            print(f"    {response.text[:500]}")
            return None
        
        # Try to parse based on format
        start_time = time.time()
        building_count = 0
        
        if format_name == 'citygml':
            # Save for inspection
            with open(f'/tmp/ogc_response_{format_name}.xml', 'wb') as f:
                f.write(response.content)
            print(f"  Response saved to /tmp/ogc_response_{format_name}.xml")
            
            gdf = parse_citygml_simple(response.content)
            building_count = len(gdf) if gdf is not None else 0
            
        elif format_name in ['cityjson', 'cityjsonseq']:
            # Save for inspection
            with open(f'/tmp/ogc_response_{format_name}.json', 'wb') as f:
                f.write(response.content)
            print(f"  Response saved to /tmp/ogc_response_{format_name}.json")
            
            # Try to count buildings from JSON
            import json
            try:
                data = json.loads(response.content)
                if 'CityObjects' in data:
                    building_count = len(data['CityObjects'])
                elif 'features' in data:
                    building_count = len(data['features'])
                print(f"  Buildings found in JSON: {building_count}")
            except:
                print(f"  Could not parse JSON structure")
                
        elif format_name == 'glb':
            # Save for inspection
            with open(f'/tmp/ogc_response_{format_name}.glb', 'wb') as f:
                f.write(response.content)
            print(f"  Response saved to /tmp/ogc_response_{format_name}.glb")
            print(f"  Note: GLB is a binary format (glTF), cannot parse building count")
            building_count = -1  # Unknown
            
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
        print(f"✗ Request failed: {e}")
        return None


def parse_citygml_simple(xml_content: bytes):
    """Simplified CityGML parser for testing."""
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
            gdf = gpd.GeoDataFrame(buildings, crs="EPSG:4326")
            return gdf
        else:
            return None
    except Exception as e:
        print(f"  Error parsing CityGML: {e}")
        return None


def main():
    """Run all tests and compare results."""
    print("="*80)
    print("API FORMAT COMPARISON TEST")
    print("="*80)
    print(f"Test area: Bonn city center")
    print(f"  WGS84 bbox: {TEST_BBOX_WGS84}")
    print(f"  EPSG:25832 bbox: {TEST_BBOX_EPSG25832}")
    
    results = []
    
    # Test 1: WFS API
    result = test_wfs_api_corrected()
    if result:
        results.append(result)
    
    # Test 2: OGC API with different formats
    formats_to_test = [
        ('citygml', 'xml'),
        ('cityjson', 'json'),
        ('cityjsonseq', 'cityjsonseq'),
        ('glb', 'glb')
    ]
    
    for format_name, f_param in formats_to_test:
        result = test_ogc_format(format_name, f_param)
        if result:
            results.append(result)
    
    # Summary comparison
    if results:
        print("\n" + "="*80)
        print("SUMMARY COMPARISON")
        print("="*80)
        print(f"\n{'Format':<20} {'Request Time':<15} {'Parse Time':<12} {'Total':<10} {'Size (KB)':<12} {'Buildings':<10}")
        print("-"*80)
        
        for r in results:
            size_kb = r['response_size'] / 1024
            bldg_count = r['building_count'] if r['building_count'] >= 0 else 'N/A'
            print(f"{r['format']:<20} {r['request_time']:>10.2f}s     {r['parse_time']:>7.2f}s     {r['total_time']:>7.2f}s   {size_kb:>8.1f}     {bldg_count}")
        
        # Find fastest
        if len(results) > 1:
            fastest = min(results, key=lambda x: x['total_time'])
            smallest = min(results, key=lambda x: x['response_size'])
            
            print("\n" + "="*80)
            print(f"⚡ FASTEST: {fastest['format']} ({fastest['total_time']:.2f}s)")
            print(f"📦 SMALLEST: {smallest['format']} ({smallest['response_size']/1024:.1f} KB)")
            
            # Calculate speed-ups
            if any(r['format'] == 'WFS GML' for r in results):
                wfs_time = next(r['total_time'] for r in results if r['format'] == 'WFS GML')
                print(f"\nSpeed comparison vs WFS:")
                for r in results:
                    if r['format'] != 'WFS GML':
                        ratio = r['total_time'] / wfs_time
                        if ratio > 1:
                            print(f"  {r['format']}: {ratio:.1f}x SLOWER")
                        else:
                            print(f"  {r['format']}: {1/ratio:.1f}x FASTER")


if __name__ == '__main__':
    main()
