#!/usr/bin/env python3
"""
Test different 3D building data sources for NRW:

1. WFS API (simple 2D footprints, fast but no heights)
2. OGC 3D API - CityGML format (LOD2, accurate but VERY slow)
3. OGC 3D API - CityJSON format (LOD2, might be faster)
4. OGC 3D API - GLB format (LOD2, binary)
5. I3S Scene Server (LOD2, optimized for streaming - visualization only)

Goal: Find the fastest way to get building heights for optimization.
"""

import requests
import time
import json

# Test area: Same bbox for all tests (Bonn city center)
TEST_BBOX_WGS84 = (7.0950, 50.7340, 7.0980, 50.7360)
TEST_BBOX_EPSG25832 = (365569.0, 5621975.9, 365786.4, 5622192.8)


def test_service(name, url, params, expected_format='unknown'):
    """Generic service tester."""
    print(f"\n{'='*80}")
    print(f"Testing: {name}")
    print(f"{'='*80}")
    print(f"URL: {url}")
    print(f"Params: {params}")
    
    try:
        start = time.time()
        response = requests.get(url, params=params, timeout=60)
        elapsed = time.time() - start
        
        status = '✓' if response.status_code == 200 else '✗'
        print(f"\n{status} Status: {response.status_code}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Size: {len(response.content):,} bytes ({len(response.content)/1024:.1f} KB)")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        
        if response.status_code == 200:
            # Try to extract building count
            building_count = None
            
            if expected_format == 'json':
                try:
                    data = json.loads(response.content)
                    if 'features' in data:
                        building_count = len(data['features'])
                    elif 'CityObjects' in data:
                        building_count = len(data['CityObjects'])
                except:
                    pass
            
            if building_count is not None:
                print(f"  Buildings: {building_count}")
            
            return {
                'name': name,
                'time': elapsed,
                'size': len(response.content),
                'buildings': building_count,
                'success': True
            }
        else:
            print(f"  Error: {response.text[:200]}")
            return {
                'name': name,
                'time': elapsed,
                'size': len(response.content),
                'buildings': None,
                'success': False
            }
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return {
            'name': name,
            'time': None,
            'size': None,
            'buildings': None,
            'success': False
        }


def main():
    print("="*80)
    print("NRW 3D BUILDING DATA SOURCES COMPARISON")
    print("="*80)
    print(f"Test area: Bonn city center")
    print(f"  WGS84: {TEST_BBOX_WGS84}")
    print(f"  EPSG:25832: {TEST_BBOX_EPSG25832}")
    
    results = []
    
    # Test 1: WFS API (baseline - fast but no heights)
    min_x, min_y, max_x, max_y = TEST_BBOX_EPSG25832
    result = test_service(
        "WFS API (2D footprints, no heights)",
        "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht",
        {
            'service': 'WFS',
            'version': '2.0.0',
            'request': 'GetFeature',
            'typeName': 'ave:GebaeudeBauwerk',
            'outputFormat': 'application/gml+xml; version=3.2',
            'srsName': 'EPSG:25832',
            'BBOX': f"{min_x},{min_y},{max_x},{max_y}"
        }
    )
    if result['success']:
        results.append(result)
    
    # Test 2: OGC API - CityGML (default, very slow)
    min_lon, min_lat, max_lon, max_lat = TEST_BBOX_WGS84
    bbox_str = f"{min_lon},{min_lat},{max_lon},{max_lat}"
    
    result = test_service(
        "OGC 3D API - CityGML/XML (LOD2, default)",
        "https://ogc-api.nrw.de/3dg/v1/collections/building/items",
        {
            'bbox': bbox_str,
            'limit': 1000
        }
    )
    if result['success']:
        results.append(result)
    
    # Test 3: OGC API - CityJSON
    result = test_service(
        "OGC 3D API - CityJSON (LOD2)",
        "https://ogc-api.nrw.de/3dg/v1/collections/building/items",
        {
            'bbox': bbox_str,
            'f': 'cityjson',
            'limit': 1000
        },
        expected_format='json'
    )
    if result['success']:
        results.append(result)
    
    # Test 4: OGC API - GLB (binary glTF)
    result = test_service(
        "OGC 3D API - GLB (LOD2, binary)",
        "https://ogc-api.nrw.de/3dg/v1/collections/building/items",
        {
            'bbox': bbox_str,
            'f': 'glb',
            'limit': 1000
        }
    )
    if result['success']:
        results.append(result)
    
    # Test 5: Check if there's a simpler query endpoint
    result = test_service(
        "OGC 3D API - Test JSON format",
        "https://ogc-api.nrw.de/3dg/v1/collections/building/items",
        {
            'bbox': bbox_str,
            'f': 'json',
            'limit': 1000
        },
        expected_format='json'
    )
    if result['success']:
        results.append(result)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if results:
        print(f"\n{'Service':<45} {'Time':<12} {'Size (KB)':<15} {'Buildings'}")
        print("-"*80)
        
        for r in results:
            time_str = f"{r['time']:.2f}s" if r['time'] else 'N/A'
            size_str = f"{r['size']/1024:.1f}" if r['size'] else 'N/A'
            bldg_str = str(r['buildings']) if r['buildings'] is not None else 'N/A'
            print(f"{r['name']:<45} {time_str:<12} {size_str:<15} {bldg_str}")
        
        # Find fastest successful service
        successful = [r for r in results if r['time'] is not None]
        if successful:
            fastest = min(successful, key=lambda x: x['time'])
            smallest = min(successful, key=lambda x: x['size'])
            
            print(f"\n{'='*80}")
            print(f"⚡ FASTEST: {fastest['name']} ({fastest['time']:.2f}s)")
            print(f"📦 SMALLEST: {smallest['name']} ({smallest['size']/1024:.1f} KB)")
            
            # Calculate relative speeds
            if len(successful) > 1:
                baseline = next((r for r in successful if 'WFS' in r['name']), successful[0])
                print(f"\nSpeed comparison vs {baseline['name']}:")
                for r in successful:
                    if r != baseline:
                        ratio = r['time'] / baseline['time']
                        if ratio > 1:
                            print(f"  {r['name']}: {ratio:.1f}x SLOWER")
                        else:
                            print(f"  {r['name']}: {1/ratio:.1f}x FASTER")
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print("""
Based on the test results:

1. If OGC CityJSON or GLB is significantly faster than CityGML:
   → Use that format for fetching building heights

2. If all OGC formats are slow (20-30+ seconds):
   → Implement dual-mode system:
     - Fast mode: WFS with estimated heights (instant)
     - Accurate mode: OGC with real heights (slow, optional)

3. If I3S Scene Server has a companion service:
   → Investigate using it for bulk attribute queries

4. Alternative approach:
   → Download entire NRW dataset once, cache locally in database
   → Query local database (instant)
    """)


if __name__ == '__main__':
    main()
