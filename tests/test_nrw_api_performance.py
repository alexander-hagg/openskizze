#!/usr/bin/env python3
"""
NRW Building Height API Performance Test Script

This script benchmarks different NRW API endpoints to find the fastest
and most reliable source for building height data.

Usage:
    python test_nrw_api_performance.py

Requirements:
    - requests
    - geopandas (for parsing GML/GeoJSON)
"""

import time
import requests
import json
from urllib.parse import urlencode
from typing import Dict, Optional, Tuple
import xml.etree.ElementTree as ET

# =============================================================================
# Test Configuration
# =============================================================================

# Test area: Bonn city center, ~1 km²
TEST_BBOX_WGS84 = (7.09, 50.73, 7.10, 50.74)  # (min_lon, min_lat, max_lon, max_lat)
TEST_BBOX_EPSG25832 = (356000, 5622000, 357000, 5623000)  # (min_x, min_y, max_x, max_y)

# Format BBOX for different API styles
BBOX_WGS84_STR = f"{TEST_BBOX_WGS84[0]},{TEST_BBOX_WGS84[1]},{TEST_BBOX_WGS84[2]},{TEST_BBOX_WGS84[3]}"
BBOX_EPSG25832_STR = f"{TEST_BBOX_EPSG25832[0]},{TEST_BBOX_EPSG25832[1]},{TEST_BBOX_EPSG25832[2]},{TEST_BBOX_EPSG25832[3]},EPSG:25832"

# Test parameters
MAX_FEATURES = 1000
TIMEOUT_SECONDS = 120

# =============================================================================
# API Endpoint Definitions
# =============================================================================

# API 1: Current WFS ALKIS Simplified (no height data)
WFS_ALKIS_URL = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
WFS_ALKIS_TYPENAME = "ave:GebaeudeBauwerk"

# API 2: OGC API 3D Buildings (has height, but slow)
OGC_3D_BASE = "https://ogc-api.nrw.de/3dg/v1"
OGC_3D_COLLECTION = "building"

# API 3: WFS 3D Buildings (if exists - to be tested)
WFS_3D_URL = "https://www.wfs.nrw.de/geobasis/wfs_nw_3d_gebauede"  # Hypothetical
WFS_3D_TYPENAME = "nw_3d:gebaeude"  # Hypothetical

# =============================================================================
# Test Functions
# =============================================================================

def measure_request(func):
    """Decorator to measure request timing and handle errors."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            total_time = time.time() - start_time
            
            if result is not None:
                result['total_time'] = total_time
                result['success'] = True
            else:
                result = {'success': False, 'total_time': total_time, 'error': 'No data returned'}
            
            return result
        except Exception as e:
            total_time = time.time() - start_time
            return {
                'success': False,
                'total_time': total_time,
                'error': str(e)
            }
    return wrapper

@measure_request
def test_wfs_alkis_simplified(bbox: str = BBOX_EPSG25832_STR) -> Optional[Dict]:
    """
    Test 1: Current WFS ALKIS Simplified endpoint (no height data).
    Expected: Fast, but no height information.
    """
    print("\n" + "="*80)
    print("TEST 1: WFS ALKIS Simplified (Current)")
    print("="*80)
    print(f"Endpoint: {WFS_ALKIS_URL}")
    print(f"Feature Type: {WFS_ALKIS_TYPENAME}")
    
    params = {
        'service': 'WFS',
        'version': '1.1.0',
        'request': 'GetFeature',
        'typeName': WFS_ALKIS_TYPENAME,
        'outputFormat': 'text/xml; subtype=gml/3.2.1',
        'srsName': 'EPSG:25832',
        'BBOX': bbox,
        'maxFeatures': MAX_FEATURES
    }
    
    ttfb_start = time.time()
    response = requests.get(WFS_ALKIS_URL, params=params, timeout=TIMEOUT_SECONDS, stream=True)
    ttfb = time.time() - ttfb_start
    
    response.raise_for_status()
    
    # Read full response
    content = response.content
    data_size_kb = len(content) / 1024
    
    # Parse to count features
    try:
        root = ET.fromstring(content)
        # Count building elements (adjust namespace as needed)
        features = root.findall('.//{*}GebaeudeBauwerk')
        num_features = len(features)
        
        # Check for height-related attributes
        height_attrs = []
        if features:
            sample = features[0]
            for elem in sample.iter():
                tag = elem.tag.split('}')[-1].lower()
                if any(h in tag for h in ['hoehe', 'height', 'geschoss', 'floor', 'dach']):
                    height_attrs.append(elem.tag)
        
    except Exception as e:
        num_features = -1
        height_attrs = []
        print(f"  Warning: Could not parse GML: {e}")
    
    print(f"  ✓ Response received")
    print(f"  TTFB: {ttfb:.3f}s")
    print(f"  Data size: {data_size_kb:.2f} KB")
    print(f"  Features: {num_features}")
    print(f"  Height attributes found: {height_attrs if height_attrs else 'NONE'}")
    
    return {
        'api_name': 'WFS ALKIS Simplified',
        'ttfb': ttfb,
        'data_size_kb': data_size_kb,
        'num_features': num_features,
        'has_height': len(height_attrs) > 0,
        'height_attrs': height_attrs
    }

@measure_request
def test_ogc_3d_api(bbox: Tuple[float, float, float, float] = TEST_BBOX_WGS84) -> Optional[Dict]:
    """
    Test 2: OGC API 3D Buildings endpoint (has measuredHeight, but slow).
    Expected: Slow initial response, but has real height data.
    """
    print("\n" + "="*80)
    print("TEST 2: OGC API 3D Buildings (LOD2)")
    print("="*80)
    print(f"Endpoint: {OGC_3D_BASE}")
    print(f"Collection: {OGC_3D_COLLECTION}")
    
    url = f"{OGC_3D_BASE}/collections/{OGC_3D_COLLECTION}/items"
    
    # Try different parameter combinations
    # NOTE: API returns CityGML/GML by default, 'f=xml' causes 400 error
    test_configs = [
        {
            'name': '2a: With bbox parameter (default GML)',
            'params': {
                'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
                'limit': MAX_FEATURES
            }
        },
        {
            'name': '2b: Without bbox (unlimited)',
            'params': {
                'limit': MAX_FEATURES
            }
        },
        {
            'name': '2c: With CQL filter (if supported)',
            'params': {
                'filter': f"BBOX(geometry,{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})",
                'filter-lang': 'cql-text',
                'limit': MAX_FEATURES
            }
        }
    ]
    
    best_result = None
    best_time = float('inf')
    
    for config in test_configs:
        print(f"\n  Testing: {config['name']}")
        
        try:
            ttfb_start = time.time()
            response = requests.get(url, params=config['params'], timeout=TIMEOUT_SECONDS, stream=True)
            ttfb = time.time() - ttfb_start
            
            response.raise_for_status()
            
            content = response.content
            data_size_kb = len(content) / 1024
            total_time = time.time() - ttfb_start
            
            # Parse CityGML to extract buildings and heights
            try:
                root = ET.fromstring(content)
                ns = {
                    'bldg': 'http://www.opengis.net/citygml/building/1.0',
                    'gml': 'http://www.opengis.net/gml'
                }
                buildings = root.findall('.//bldg:Building', ns)
                num_features = len(buildings)
                
                # Extract height statistics
                heights = []
                for bldg in buildings:
                    height_elem = bldg.find('.//bldg:measuredHeight', ns)
                    if height_elem is not None and height_elem.text:
                        try:
                            heights.append(float(height_elem.text))
                        except ValueError:
                            pass
                
                has_height = len(heights) > 0
                height_stats = None
                if heights:
                    height_stats = {
                        'min': min(heights),
                        'max': max(heights),
                        'mean': sum(heights) / len(heights),
                        'coverage': len(heights) / num_features
                    }
                
            except Exception as e:
                num_features = -1
                has_height = False
                height_stats = None
                print(f"    Warning: Could not parse CityGML: {e}")
            
            print(f"    ✓ Response received")
            print(f"    TTFB: {ttfb:.3f}s")
            print(f"    Total time: {total_time:.3f}s")
            print(f"    Data size: {data_size_kb:.2f} KB")
            print(f"    Features: {num_features}")
            if height_stats:
                print(f"    Heights: {height_stats['min']:.1f}m - {height_stats['max']:.1f}m (mean: {height_stats['mean']:.1f}m)")
                print(f"    Coverage: {height_stats['coverage']*100:.1f}% buildings have height")
            
            result = {
                'api_name': f'OGC 3D API - {config["name"]}',
                'ttfb': ttfb,
                'data_size_kb': data_size_kb,
                'num_features': num_features,
                'has_height': has_height,
                'height_stats': height_stats
            }
            
            if total_time < best_time:
                best_time = total_time
                best_result = result
                
        except Exception as e:
            print(f"    ✗ Failed: {e}")
            continue
    
    return best_result

@measure_request
def test_wfs_capabilities_analysis() -> Optional[Dict]:
    """
    Test 3: Analyze WFS GetCapabilities to find all available height-related properties.
    """
    print("\n" + "="*80)
    print("TEST 3: WFS Capabilities Analysis")
    print("="*80)
    print("Analyzing all WFS endpoints for height data...")
    
    wfs_endpoints = [
        ("ALKIS Simplified", WFS_ALKIS_URL),
        ("3D Buildings (hypothetical)", WFS_3D_URL),
    ]
    
    results = {}
    
    for name, url in wfs_endpoints:
        print(f"\n  Checking: {name}")
        print(f"  URL: {url}")
        
        try:
            params = {
                'service': 'WFS',
                'request': 'GetCapabilities'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse capabilities XML
            root = ET.fromstring(response.content)
            
            # Find all feature types and their properties
            feature_types = []
            for ft in root.findall('.//{*}FeatureType'):
                name_elem = ft.find('{*}Name')
                if name_elem is not None:
                    ft_name = name_elem.text
                    feature_types.append(ft_name)
            
            print(f"    ✓ Found {len(feature_types)} feature types")
            
            # Look for height-related feature types
            height_related = [ft for ft in feature_types if any(
                keyword in ft.lower() for keyword in 
                ['3d', 'hoehe', 'height', 'gebaeude', 'building', 'geschoss']
            )]
            
            if height_related:
                print(f"    Height-related types: {height_related}")
            else:
                print(f"    No obvious height-related types found")
            
            results[name] = {
                'success': True,
                'feature_types': feature_types,
                'height_related': height_related
            }
            
        except Exception as e:
            print(f"    ✗ Failed: {e}")
            results[name] = {'success': False, 'error': str(e)}
    
    return results

# =============================================================================
# Main Test Execution
# =============================================================================

def run_all_tests():
    """Execute all API performance tests and generate comparison report."""
    print("="*80)
    print("NRW BUILDING HEIGHT API PERFORMANCE TESTS")
    print("="*80)
    print(f"Test Area: Bonn city center (~1 km²)")
    print(f"BBOX (WGS84): {BBOX_WGS84_STR}")
    print(f"BBOX (EPSG:25832): {BBOX_EPSG25832_STR}")
    print(f"Max Features: {MAX_FEATURES}")
    print(f"Timeout: {TIMEOUT_SECONDS}s")
    
    results = []
    
    # Test 1: Current WFS ALKIS
    result1 = test_wfs_alkis_simplified()
    if result1:
        results.append(result1)
    
    # Test 2: OGC API 3D
    result2 = test_ogc_3d_api()
    if result2:
        results.append(result2)
    
    # Test 3: Capabilities analysis
    result3 = test_wfs_capabilities_analysis()
    
    # Generate summary report
    print("\n" + "="*80)
    print("SUMMARY REPORT")
    print("="*80)
    
    # Sort by total time (fastest first)
    results_sorted = sorted([r for r in results if r['success']], 
                           key=lambda x: x['total_time'])
    
    print("\nPerformance Ranking (fastest to slowest):")
    print("-" * 80)
    for i, result in enumerate(results_sorted, 1):
        print(f"\n{i}. {result['api_name']}")
        print(f"   Total Time: {result['total_time']:.3f}s")
        print(f"   TTFB: {result['ttfb']:.3f}s")
        print(f"   Data Size: {result['data_size_kb']:.2f} KB")
        print(f"   Features: {result['num_features']}")
        print(f"   Has Height: {'✓ YES' if result.get('has_height') else '✗ NO'}")
        
        if result.get('height_stats'):
            stats = result['height_stats']
            print(f"   Height Range: {stats['min']:.1f}m - {stats['max']:.1f}m")
            print(f"   Height Coverage: {stats['coverage']*100:.1f}%")
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    # Find best option with height data
    with_height = [r for r in results_sorted if r.get('has_height')]
    without_height = [r for r in results_sorted if not r.get('has_height')]
    
    if with_height:
        best_with_height = with_height[0]
        print(f"\n✓ RECOMMENDED: {best_with_height['api_name']}")
        print(f"  - Has height data: YES")
        print(f"  - Response time: {best_with_height['total_time']:.3f}s")
        if best_with_height['total_time'] > 10:
            print(f"  ⚠ WARNING: Response time > 10s may be too slow for production")
    
    if without_height and without_height[0]['total_time'] < 5:
        fastest = without_height[0]
        print(f"\n⚡ FASTEST (no height): {fastest['api_name']}")
        print(f"  - Response time: {fastest['total_time']:.3f}s")
        print(f"  - Consider using with estimated heights from building function")
    
    print("\n" + "="*80)
    
    return results

if __name__ == "__main__":
    try:
        results = run_all_tests()
        print("\n✓ All tests completed successfully")
    except KeyboardInterrupt:
        print("\n\n✗ Tests interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
