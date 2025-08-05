# backend/data_io.py

import requests
import json
import geopandas
from shapely.geometry import box
import io

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
        print(f"An error occurred during Flurstücke fetching: {e}")
        return None

# --- Existing Buildings Fetching (New Function) ---
WFS_URL_BUILDINGS = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
TYPE_NAME_BUILDINGS = "ave:GebaeudeBauwerk"

def fetch_existing_buildings_data(bbox: tuple):
    """
    Fetches existing building footprints from the NRW WFS API for a given bounding box.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
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