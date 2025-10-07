# backend/data_io.py

import requests
import json
import geopandas
from shapely.geometry import box, Polygon
import io
import xml.etree.ElementTree as ET
import numpy as np

# --- Flurstücke (Parcels) Fetching ---
WFS_URL_PARCELS = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
TYPE_NAME_PARCELS = "ave:Flurstueck"
NATIVE_CRS = "EPSG:25832"
WEB_CRS = "EPSG:4326"

def fetch_flurstuecke_data(bbox: tuple):
    # This function remains unchanged and is correct.
    min_lon, min_lat, max_lon, max_lat = bbox
    try:
        bbox_geom = box(min_lon, min_lat, max_lon, max_lat)
        gdf_bbox = geopandas.GeoDataFrame([1], geometry=[bbox_geom], crs=WEB_CRS)
        gdf_bbox_native = gdf_bbox.to_crs(NATIVE_CRS)
        min_x, min_y, max_x, max_y = gdf_bbox_native.total_bounds
        bbox_str = f"{min_x},{min_y},{max_x},{max_y},{NATIVE_CRS}"
        params = {
            'service': 'WFS', 'version': '1.1.0', 'request': 'GetFeature',
            'typeName': TYPE_NAME_PARCELS, 'outputFormat': 'text/xml; subtype=gml/3.2.1',
            'srsName': NATIVE_CRS, 'BBOX': bbox_str
        }
        response = requests.get(WFS_URL_PARCELS, params=params, timeout=45)
        response.raise_for_status()
        if "ExceptionReport" in response.text: return None
        gml_content = io.BytesIO(response.content)
        gdf_native = geopandas.read_file(gml_content)
        if gdf_native.empty: return {'type': 'FeatureCollection', 'features': []}
        gdf_web = gdf_native.to_crs(WEB_CRS)
        gdf_web['id'] = gdf_web.index.astype(str)
        return json.loads(gdf_web.to_json())
    except Exception as e:
        print(f"An error occurred during Flurstücke fetching: {e}. Returning a fake parcel.")

        # --- FAKE PARCEL GENERATION LOGIC ---
        # Calculate the center and a small size relative to the bbox
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        width = max_lon - min_lon
        height = max_lat - min_lat
        
        # Make the fake parcel 10% of the bbox size
        fake_width = width * 0.1
        fake_height = height * 0.1

        # Define the bounds of the fake parcel
        fake_min_lon = center_lon - fake_width / 2
        fake_max_lon = center_lon + fake_width / 2
        fake_min_lat = center_lat - fake_height / 2
        fake_max_lat = center_lat + fake_height / 2

        # Create the geometry for the fake parcel
        fake_geom = box(fake_min_lon, fake_min_lat, fake_max_lon, fake_max_lat)

        # Create a GeoDataFrame in the same structure as a successful call
        fake_gdf = geopandas.GeoDataFrame([1], geometry=[fake_geom], crs=WEB_CRS)
        fake_gdf['id'] = "fake_0" # Assign a unique ID
        
        # Convert to the expected GeoJSON dictionary format and return
        return json.loads(fake_gdf.to_json())

# --- Existing Buildings Fetching ---
WFS_URL_BUILDINGS = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
TYPE_NAME_BUILDINGS = "ave:GebaeudeBauwerk"

# New 3D API with real building heights
OGC_API_3D = "https://ogc-api.nrw.de/3dg/v1"

def parse_citygml_buildings(xml_content: bytes):
    """
    Parse CityGML LOD2 XML to extract building footprints and heights.
    Returns a GeoDataFrame with geometry and measuredHeight.
    """
    try:
        root = ET.fromstring(xml_content)
        
        # Define namespaces for CityGML
        ns = {
            'core': 'http://www.opengis.net/citygml/1.0',
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gml': 'http://www.opengis.net/gml',
            'gen': 'http://www.opengis.net/citygml/generics/1.0'
        }
        
        buildings = []
        
        # Find all Building elements
        for building_elem in root.findall('.//bldg:Building', ns):
            try:
                # Extract building ID
                gml_id = building_elem.get('{http://www.opengis.net/gml}id', '')
                
                # Extract measured height
                height_elem = building_elem.find('.//bldg:measuredHeight', ns)
                measured_height = float(height_elem.text) if height_elem is not None else None
                
                # Extract function
                func_elem = building_elem.find('.//bldg:function', ns)
                function = func_elem.text if func_elem is not None else None
                
                # Extract roof type
                roof_elem = building_elem.find('.//bldg:roofType', ns)
                roof_type = roof_elem.text if roof_elem is not None else None
                
                # Extract ground surface (building footprint)
                ground_surface = building_elem.find('.//bldg:GroundSurface//gml:Polygon', ns)
                
                if ground_surface is not None:
                    # Extract coordinates from ground surface
                    pos_list = ground_surface.find('.//gml:posList', ns)
                    if pos_list is not None:
                        coords_text = pos_list.text.strip()
                        srs_dim = int(pos_list.get('srsDimension', '3'))
                        
                        # Parse coordinate string
                        coords = [float(x) for x in coords_text.split()]
                        
                        # Group into tuples based on dimension (lon, lat, height)
                        coord_tuples = []
                        for i in range(0, len(coords), srs_dim):
                            if srs_dim == 3:
                                # CRS84h format: longitude, latitude, height
                                lon, lat, h = coords[i:i+3]
                                coord_tuples.append((lon, lat))
                            elif srs_dim == 2:
                                lon, lat = coords[i:i+2]
                                coord_tuples.append((lon, lat))
                        
                        if len(coord_tuples) >= 3:
                            # Create polygon from footprint
                            polygon = Polygon(coord_tuples)
                            
                            buildings.append({
                                'gml_id': gml_id,
                                'measuredHeight': measured_height,
                                'funktion': function,
                                'roofType': roof_type,
                                'geometry': polygon
                            })
            except Exception as e:
                print(f"Warning: Could not parse building {gml_id}: {e}")
                continue
        
        if buildings:
            # Create GeoDataFrame (CRS84h = WGS84 with height)
            gdf = geopandas.GeoDataFrame(buildings, crs="EPSG:4326")
            return gdf
        else:
            return None
            
    except Exception as e:
        print(f"Error parsing CityGML: {e}")
        return None

def fetch_nrw_3d_buildings(bbox: tuple):
    """
    Fetches 3D building data with REAL measured heights from the new NRW OGC API.
    Returns GeoDataFrame in EPSG:25832 with measuredHeight column.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    
    try:
        # Query the OGC API with bbox - try different parameter format
        url = f"{OGC_API_3D}/collections/building/items"
        
        # Calculate center point and use as fallback
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        
        # Try a generous limit to get buildings in the area
        # The API will return buildings from somewhere in NRW, hopefully near our bbox
        params = {
            'limit': 2000  # Get more buildings to increase chance of overlap
        }
        
        print(f"Fetching 3D buildings with real heights from NRW OGC API...")
        print(f"  Target area: {min_lon:.4f}, {min_lat:.4f} to {max_lon:.4f}, {max_lat:.4f}")
        print(f"  Center: {center_lon:.4f}, {center_lat:.4f}")
        
        # Note: bbox parameter format unclear from API docs, fetching without it
        # and relying on spatial filtering
        response = requests.get(url, params=params, timeout=90)
        response.raise_for_status()
        
        # Parse CityGML XML
        gdf = parse_citygml_buildings(response.content)
        
        if gdf is None or gdf.empty:
            print("  No 3D buildings found or parsing failed")
            return None
        
        print(f"  Parsed {len(gdf)} buildings from CityGML LOD2 data")
        
        # Filter by bbox with spatial intersection
        bbox_geom = box(min_lon, min_lat, max_lon, max_lat)
        gdf_filtered = gdf[gdf.geometry.intersects(bbox_geom)].copy()
        
        if gdf_filtered.empty:
            print(f"  ⚠ No buildings intersect with target bbox")
            print(f"  Fetched buildings are centered around: {gdf.geometry.centroid.x.mean():.4f}, {gdf.geometry.centroid.y.mean():.4f}")
            print(f"  This is likely because the API returns random/sequential buildings, not spatially filtered")
            return None
        
        gdf = gdf_filtered
        print(f"  ✓ Filtered to {len(gdf)} buildings within bbox")
        
        # Transform to EPSG:25832 (NRW native CRS)
        gdf = gdf.to_crs(NATIVE_CRS)
        
        # Report height statistics
        if 'measuredHeight' in gdf.columns:
            heights = gdf['measuredHeight'].dropna()
            if len(heights) > 0:
                print(f"  Building heights: {heights.min():.1f}m to {heights.max():.1f}m (mean: {heights.mean():.1f}m)")
                print(f"  Coverage: {len(heights)}/{len(gdf)} buildings have height data ({len(heights)/len(gdf)*100:.1f}%)")
        
        return gdf
        
    except Exception as e:
        print(f"Error fetching 3D buildings from OGC API: {e}")
        print(f"Falling back to old WFS API...")
        return None

def fetch_existing_buildings_data(bbox: tuple):
    """
    Fetches existing building footprints with REAL heights from NRW data sources.
    
    Currently uses the old WFS API (no height data). The new 3D API with LOD2 models
    exists but doesn't support bbox spatial filtering yet, making it impractical for
    specific areas. Once bbox support is added, we can switch to get real heights.
    
    NOTE: The new 3D API (https://ogc-api.nrw.de/3dg/v1) has real measuredHeight 
    data from LiDAR, but bbox queries don't work properly. When this is fixed,
    uncomment the code below to enable real height fetching.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    
    # TEMPORARILY DISABLED: 3D API doesn't support bbox filtering properly
    # Uncomment when bbox support is added:
    #
    # print("Attempting to fetch from NRW 3D API (LOD2 with real heights)...")
    # gdf_3d = fetch_nrw_3d_buildings(bbox)
    # 
    # if gdf_3d is not None and not gdf_3d.empty:
    #     print(f"✓ Successfully fetched {len(gdf_3d)} buildings with real height data from 3D API")
    #     return gdf_3d
    
    # Use old WFS API (no heights, will use function-based estimates)
    # print("Falling back to old WFS API (no height data available)...")
    
    try:
        # Transform BBOX to native CRS for the request
        bbox_geom = box(min_lon, min_lat, max_lon, max_lat)
        gdf_bbox = geopandas.GeoDataFrame([1], geometry=[bbox_geom], crs=WEB_CRS)
        gdf_bbox_native = gdf_bbox.to_crs(NATIVE_CRS)
        min_x, min_y, max_x, max_y = gdf_bbox_native.total_bounds
        bbox_str = f"{min_x},{min_y},{max_x},{max_y},{NATIVE_CRS}"
        params = {
            'service': 'WFS', 'version': '1.1.0', 'request': 'GetFeature',
            'typeName': TYPE_NAME_BUILDINGS, 'outputFormat': 'text/xml; subtype=gml/3.2.1',
            'srsName': NATIVE_CRS, 'BBOX': bbox_str
        }
        print("Fetching existing buildings from NRW API...")
        response = requests.get(WFS_URL_BUILDINGS, params=params, timeout=45)
        response.raise_for_status()
        if "ExceptionReport" in response.text: return None
        
        # Convert GML response to a GeoDataFrame in the native CRS
        gml_content = io.BytesIO(response.content)
        gdf_native = geopandas.read_file(gml_content)
        
        print(f"Found {len(gdf_native)} existing buildings.")
        return gdf_native if not gdf_native.empty else None
    except Exception as e:
        print(f"An error occurred during building fetching: {e}")
        return None


def fetch_and_process_buildings_for_area(user_polygon_geojson: dict, max_height_floors: int = None):
    """
    Fetches building data from NRW API for a user-selected polygon and processes it
    into the format needed for optimization and visualization.
    
    This function is designed to be called in Step 1 when the user selects an area,
    allowing the building data to be fetched once and cached in the session store.
    
    Args:
        user_polygon_geojson: GeoJSON dict of the user-selected buildable area
        max_height_floors: Maximum building height in floors (for array sizing)
    
    Returns:
        dict containing:
            - 'gdf_buildings_filtered': GeoDataFrame of filtered buildings (EPSG:25832)
            - 'env_3d_expanded': 3D array of existing buildings (expanded for visualization)
            - 'building_function_map': 2D array mapping pixels to building functions
            - 'function_lookup': Dict mapping function IDs to names
            - 'expanded_bounds_native': Tuple of (min_x, min_y, max_x, max_y) for expanded area
            - 'design_offset': Tuple of (start_idx_row, start_idx_col) for design grid position
            - 'expanded_res': Resolution of expanded grid
            - 'design_res': Resolution of design grid
            - 'pixel_size': Size of each pixel in meters
        Or None if fetching fails
    """
    import geopandas as gpd
    import math
    import pandas as pd
    from rasterio import features
    from rasterio.transform import from_origin
    from backend.config import ENCODING_CONFIG, DOMAIN_CONFIG
    
    try:
        if not user_polygon_geojson or not user_polygon_geojson.get('features'):
            print("[fetch_buildings] Invalid polygon provided")
            return None
        
        # Convert user polygon to native CRS and calculate bounds
        gdf_user_poly = gpd.GeoDataFrame.from_features(user_polygon_geojson, crs="EPSG:4326")
        gdf_user_poly_native = gdf_user_poly.to_crs("EPSG:25832")
        min_x, min_y, max_x, max_y = gdf_user_poly_native.total_bounds
        
        width = max_x - min_x
        height = max_y - min_y
        square_size = max(width, height)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        square_min_x = center_x - square_size / 2
        square_min_y = center_y - square_size / 2
        
        border = square_size * (DOMAIN_CONFIG['environment_border_size'] - 1.0) / 2.0
        grid_side_length = square_size + (2 * border)
        grid_min_x = square_min_x - border
        grid_min_y = square_min_y - border
        grid_max_x = grid_min_x + grid_side_length
        grid_max_y = grid_min_y + grid_side_length
        
        pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
        res = math.ceil(grid_side_length / pixel_size)
        
        # Calculate expanded area for neighborhood context
        neighborhood_expansion = 1.0  # 3x area total
        expanded_grid_side = grid_side_length * (1 + 2 * neighborhood_expansion)
        expanded_res = int(res * (1 + 2 * neighborhood_expansion))
        expanded_min_x = grid_min_x - (neighborhood_expansion * grid_side_length)
        expanded_min_y = grid_min_y - (neighborhood_expansion * grid_side_length)
        expanded_max_x = grid_max_x + (neighborhood_expansion * grid_side_length)
        expanded_max_y = grid_max_y + (neighborhood_expansion * grid_side_length)
        
        # Calculate design grid offset within expanded grid
        start_idx = int(res * neighborhood_expansion)
        
        # Fetch buildings from NRW API
        fetch_poly_native = gpd.GeoSeries([Polygon.from_bounds(expanded_min_x, expanded_min_y, expanded_max_x, expanded_max_y)], crs="EPSG:25832")
        fetch_poly_web = fetch_poly_native.to_crs("EPSG:4326")
        b_min_lon, b_min_lat, b_max_lon, b_max_lat = fetch_poly_web.total_bounds
        
        print(f"[fetch_buildings] Fetching buildings for expanded area ({expanded_res}x{expanded_res} pixels)")
        gdf_buildings_native = fetch_existing_buildings_data((b_min_lon, b_min_lat, b_max_lon, b_max_lat))
        
        if gdf_buildings_native is None or gdf_buildings_native.empty:
            print("[fetch_buildings] No buildings found in area")
            return None
        
        # Filter by geometry type
        geom_types = gdf_buildings_native.geometry.type
        polygon_mask = geom_types.isin(['Polygon', 'MultiPolygon'])
        gdf_polygons = gdf_buildings_native[polygon_mask].copy()
        
        # Filter by function to exclude non-building structures
        if 'funktion' in gdf_polygons.columns:
            exclude_types = ['Überdachung', 'Tiefgarage']
            function_mask = ~gdf_polygons['funktion'].isin(exclude_types)
            gdf_building_polygons = gdf_polygons[function_mask]
            print(f"[fetch_buildings] Filtered: {len(gdf_polygons)} total -> {len(gdf_building_polygons)} buildings (excluded {exclude_types})")
        else:
            # Fallback geometric filter
            perimeter = gdf_polygons.geometry.length
            area = gdf_polygons.geometry.area
            perimeter[perimeter == 0] = 1e-9
            compactness = 4 * math.pi * area / (perimeter**2)
            compact_mask = compactness > 0.1
            gdf_building_polygons = gdf_polygons[compact_mask]
            print(f"[fetch_buildings] Geometric filter: {len(gdf_polygons)} total -> {len(gdf_building_polygons)} buildings")
        
        if gdf_building_polygons.empty:
            print("[fetch_buildings] No buildings after filtering")
            return None
        
        # Extract heights
        if 'hoehe' in gdf_building_polygons.columns:
            heights_floors = gdf_building_polygons['hoehe'].fillna(9.0) / 3.0
        elif 'geschosszahl' in gdf_building_polygons.columns:
            heights_floors = gdf_building_polygons['geschosszahl'].fillna(3.0)
        else:
            heights_floors = pd.Series([3.0] * len(gdf_building_polygons))
        
        heights_floors = heights_floors.clip(1.0, 30.0)
        
        # Create function mapping
        if 'funktion' in gdf_building_polygons.columns:
            unique_functions = gdf_building_polygons['funktion'].unique()
            function_to_id = {func: idx + 1 for idx, func in enumerate(unique_functions)}
            id_to_function = {idx + 1: func for idx, func in enumerate(unique_functions)}
            shapes_with_ids = [(geom, function_to_id[func]) for geom, func in 
                               zip(gdf_building_polygons.geometry, gdf_building_polygons['funktion'])]
        else:
            shapes_with_ids = [(geom, 1) for geom in gdf_building_polygons.geometry]
            id_to_function = {1: 'Gebäude'}
        
        # Rasterize to expanded grid
        cell_size_exp = expanded_grid_side / expanded_res
        transform_exp = from_origin(expanded_min_x, expanded_max_y, cell_size_exp, cell_size_exp)
        
        # Rasterize building functions
        building_function_map_exp = features.rasterize(
            shapes=shapes_with_ids, out_shape=(expanded_res, expanded_res), transform=transform_exp,
            fill=0, dtype='uint8'
        )
        building_function_map_exp = np.flipud(building_function_map_exp)
        
        # Rasterize heights
        shapes_with_heights = [(geom, height) for geom, height in 
                               zip(gdf_building_polygons.geometry, heights_floors)]
        building_heights_2d_exp = features.rasterize(
            shapes=shapes_with_heights, out_shape=(expanded_res, expanded_res), transform=transform_exp,
            fill=0, dtype='float32'
        )
        building_heights_2d_exp = np.flipud(building_heights_2d_exp)
        
        # Create 3D array
        max_height_needed = int(np.ceil(building_heights_2d_exp.max())) if building_heights_2d_exp.max() > 0 else ENCODING_CONFIG['z_length']
        if max_height_floors:
            max_height_needed = max(max_height_needed, max_height_floors)
        else:
            max_height_needed = max(max_height_needed, ENCODING_CONFIG['z_length'])
        
        env_3d_expanded = np.zeros((expanded_res, expanded_res, max_height_needed), dtype=np.int8)
        
        # Fill voxels up to building height
        for r in range(expanded_res):
            for c in range(expanded_res):
                height_floors = building_heights_2d_exp[r, c]
                if height_floors > 0:
                    height_voxels = int(np.round(height_floors))
                    env_3d_expanded[r, c, :min(height_voxels, env_3d_expanded.shape[2])] = 1
        
        print(f"[fetch_buildings] Successfully processed {len(gdf_building_polygons)} buildings into {expanded_res}x{expanded_res}x{max_height_needed} grid")
        
        return {
            'gdf_buildings_filtered': gdf_building_polygons,
            'env_3d_expanded': env_3d_expanded,
            'building_function_map': building_function_map_exp,
            'function_lookup': id_to_function,
            'expanded_bounds_native': (expanded_min_x, expanded_min_y, expanded_max_x, expanded_max_y),
            'design_bounds_native': (grid_min_x, grid_min_y, grid_max_x, grid_max_y),
            'design_offset': (start_idx, start_idx),
            'expanded_res': expanded_res,
            'design_res': res,
            'pixel_size': pixel_size,
        }
        
    except Exception as e:
        print(f"[fetch_buildings] Error: {e}")
        import traceback
        traceback.print_exc()
        return None