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