#!/usr/bin/env python3
"""
Download and process LOD2 GML tile data from NRW OpenGeoData portal.

This script downloads complete 3D building data in 1km x 1km tiles,
providing full coverage unlike the OGC 3D API.
"""

import os
import math
import requests
import pandas as pd
import geopandas as gpd
import xml.etree.ElementTree as ET
from pathlib import Path
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import time

# Configuration
BASE_URL = "https://www.opengeodata.nrw.de/produkte/geobasis/3dg/lod2_gml/lod2_gml"
CACHE_DIR = Path(__file__).parent / "lod2_tiles_cache"
CACHE_DIR.mkdir(exist_ok=True)

# CityGML namespaces (NRW uses CityGML 1.0)
NAMESPACES = {
    'core': 'http://www.opengis.net/citygml/1.0',
    'bldg': 'http://www.opengis.net/citygml/building/1.0',
    'gml': 'http://www.opengis.net/gml',
    'gen': 'http://www.opengis.net/citygml/generics/1.0'
}


def bbox_to_tiles(min_x, min_y, max_x, max_y, tile_size=1000):
    """
    Convert bbox to tile grid indices.
    
    NRW uses 1km x 1km tiles with naming: LoD2_32_<X>_<Y>_1_NW.gml
    where X = easting/1000, Y = northing/1000
    
    Args:
        min_x, min_y, max_x, max_y: Bbox coordinates in EPSG:25832
        tile_size: Tile size in meters (default 1000m = 1km)
    
    Returns:
        List of (tile_x, tile_y) tuples
    """
    # Calculate tile indices
    tile_min_x = int(math.floor(min_x / tile_size))
    tile_max_x = int(math.floor(max_x / tile_size))
    tile_min_y = int(math.floor(min_y / tile_size))
    tile_max_y = int(math.floor(max_y / tile_size))
    
    # Generate all tile combinations
    tiles = []
    for x in range(tile_min_x, tile_max_x + 1):
        for y in range(tile_min_y, tile_max_y + 1):
            tiles.append((x, y))
    
    return tiles


def download_tile(tile_x, tile_y, force_reload=False):
    """
    Download a single LOD2 GML tile.
    
    Args:
        tile_x: Tile column (easting in km)
        tile_y: Tile row (northing in km)
        force_reload: If True, re-download even if cached
    
    Returns:
        Path to downloaded file, or None if download failed
    """
    filename = f"LoD2_32_{tile_x}_{tile_y}_1_NW.gml"
    cache_path = CACHE_DIR / filename
    
    # Use cache if exists and not forcing reload
    if cache_path.exists() and not force_reload:
        print(f"  ✓ Using cached: {filename}")
        return cache_path
    
    # Build download URL
    url = f"{BASE_URL}/{filename}"
    
    print(f"  ⬇ Downloading: {filename}")
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        # Save to cache
        with open(cache_path, 'wb') as f:
            f.write(response.content)
        
        print(f"    Downloaded {len(response.content) / 1024 / 1024:.1f} MB")
        return cache_path
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"    Tile not available (404)")
        else:
            print(f"    HTTP error: {e}")
        return None
    
    except Exception as e:
        print(f"    Error downloading: {e}")
        return None


def parse_citygml_tile(gml_file, bbox=None):
    """
    Parse CityGML LOD2 file and extract building footprints with heights.
    
    Args:
        gml_file: Path to GML file
        bbox: Optional (min_x, min_y, max_x, max_y) to filter buildings
    
    Returns:
        GeoDataFrame with building geometry and measuredHeight
    """
    print(f"  📄 Parsing: {gml_file.name}")
    
    try:
        tree = ET.parse(gml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"    ✗ XML parse error: {e}")
        return None
    
    buildings = []
    
    # Find all Building elements
    for building in root.findall('.//bldg:Building', NAMESPACES):
        try:
            # Extract measuredHeight
            height_elem = building.find('.//bldg:measuredHeight', NAMESPACES)
            if height_elem is None:
                continue
            
            try:
                height = float(height_elem.text)
            except (ValueError, TypeError):
                continue
            
            # Extract building ID
            gml_id = building.get('{http://www.opengis.net/gml}id', 'unknown')
            
            # Try to find footprint from lod2TerrainIntersection (2D projection)
            terrain_intersection = building.find('.//bldg:lod2TerrainIntersection//gml:posList', NAMESPACES)
            
            if terrain_intersection is not None:
                # Parse coordinates from terrain intersection
                coords_text = terrain_intersection.text.strip()
                coords = [float(x) for x in coords_text.split()]
                
                # Group into (x, y, z) tuples, then create 2D polygon
                points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 3)]
            else:
                # Fallback: Try GroundSurface from lod2Solid
                ground_surface = building.find('.//bldg:GroundSurface//gml:Polygon//gml:posList', NAMESPACES)
                if ground_surface is None:
                    continue
                
                coords_text = ground_surface.text.strip()
                coords = [float(x) for x in coords_text.split()]
                points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 3)]
            
            if len(points) < 3:
                continue
            
            # Create polygon
            polygon = Polygon(points)
            
            # Apply bbox filter if provided
            if bbox:
                bbox_poly = box(*bbox)
                if not polygon.intersects(bbox_poly):
                    continue
            
            buildings.append({
                'geometry': polygon,
                'measuredHeight': height,
                'building_id': gml_id,
                'source': 'LOD2_Tile'
            })
        
        except Exception as e:
            # Skip problematic buildings
            continue
    
    if not buildings:
        print(f"    No buildings found in tile")
        return None
    
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(buildings, crs='EPSG:25832')
    print(f"    ✓ Parsed {len(gdf)} buildings")
    
    return gdf


def fetch_lod2_tiles_for_bbox(min_x, min_y, max_x, max_y, force_reload=False):
    """
    Fetch and merge LOD2 building data from tiles covering a bounding box.
    
    Args:
        min_x, min_y, max_x, max_y: Bbox in EPSG:25832
        force_reload: If True, re-download tiles even if cached
    
    Returns:
        GeoDataFrame with all buildings in the bbox, or None if no data
    """
    print(f"\n🔍 Fetching LOD2 tiles for bbox: ({min_x}, {min_y}, {max_x}, {max_y})")
    
    # Calculate required tiles
    tiles = bbox_to_tiles(min_x, min_y, max_x, max_y)
    print(f"📦 Need {len(tiles)} tile(s): {tiles}")
    
    # Download and parse each tile
    all_buildings = []
    for tile_x, tile_y in tiles:
        print(f"\n⬛ Processing tile ({tile_x}, {tile_y})")
        
        # Download
        tile_path = download_tile(tile_x, tile_y, force_reload)
        if tile_path is None:
            continue
        
        # Parse
        gdf = parse_citygml_tile(tile_path, bbox=(min_x, min_y, max_x, max_y))
        if gdf is not None and len(gdf) > 0:
            all_buildings.append(gdf)
        
        # Be nice to the server
        time.sleep(0.5)
    
    # Merge all buildings
    if not all_buildings:
        print("\n✗ No buildings found in any tiles")
        return None
    
    merged = gpd.GeoDataFrame(pd.concat(all_buildings, ignore_index=True), crs='EPSG:25832')
    
    # Remove duplicates (buildings on tile boundaries might appear multiple times)
    original_count = len(merged)
    merged = merged.drop_duplicates(subset=['building_id'])
    
    print(f"\n✓ Total buildings: {len(merged)} (removed {original_count - len(merged)} duplicates)")
    print(f"  Height range: {merged['measuredHeight'].min():.1f}m - {merged['measuredHeight'].max():.1f}m")
    print(f"  Mean height: {merged['measuredHeight'].mean():.1f}m")
    
    return merged


def main():
    """Test the tile download system with Bonn city center."""
    import pandas as pd
    
    # Bonn test area (same as previous tests)
    bbox = (365204, 5621522, 365938, 5622652)  # EPSG:25832
    
    print("=" * 70)
    print("NRW LOD2 TILE DOWNLOAD TEST")
    print("=" * 70)
    
    # Fetch LOD2 data
    lod2_buildings = fetch_lod2_tiles_for_bbox(*bbox, force_reload=False)
    
    if lod2_buildings is None:
        print("\n✗ Failed to fetch LOD2 data")
        return
    
    print("\n" + "=" * 70)
    print("COMPARISON WITH PREVIOUS RESULTS")
    print("=" * 70)
    print(f"WFS ALKIS:   2655 buildings (complete footprints, no height)")
    print(f"OGC 3D API:  2291 buildings (incomplete, with heights)")
    print(f"LOD2 Tiles:  {len(lod2_buildings)} buildings (complete, with heights)")
    print("=" * 70)
    
    # Save results
    output_file = Path(__file__).parent / "lod2_tiles_bonn.gpkg"
    lod2_buildings.to_file(output_file, driver='GPKG')
    print(f"\n💾 Saved to: {output_file}")
    
    # Print sample
    print("\n📋 Sample buildings:")
    print(lod2_buildings[['building_id', 'measuredHeight', 'source']].head(10).to_string())


if __name__ == '__main__':
    main()
