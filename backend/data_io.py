#
# backend/data_io.py (Final Version with corrected box import)
#
import requests
import json
import geopandas
from shapely.geometry import box # FIX: Import 'box' directly from shapely.geometry
import io

# Parameters confirmed to be correct from the GetCapabilities document
WFS_URL = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
TYPE_NAME = "ave:Flurstueck"
NATIVE_CRS = "EPSG:25832"
WEB_CRS = "EPSG:4326"

def fetch_flurstuecke_data(bbox: tuple):
    """
    Fetches ALKIS Flurstücke data from the NRW "Simplified" WFS API.
    This version correctly transforms CRS and embeds a stable ID for front-end selection.

    Args:
        bbox (tuple): A tuple containing the web map's bounding box in lon/lat (EPSG:4326).

    Returns:
        dict: A GeoJSON feature collection of the Flurstücke, or None on error.
    """
    if not bbox:
        return None

    min_lon, min_lat, max_lon, max_lat = bbox

    try:
        # 1. Transform the request BBOX from Web CRS to the Server's Native CRS
        print(f"Transforming request BBOX from {WEB_CRS} to {NATIVE_CRS}...")
        # FIX: Call box() directly, not as an attribute of geopandas
        bbox_geom = box(min_lon, min_lat, max_lon, max_lat)
        gdf_bbox = geopandas.GeoDataFrame([1], geometry=[bbox_geom], crs=WEB_CRS)
        gdf_bbox_native = gdf_bbox.to_crs(NATIVE_CRS)
        min_x, min_y, max_x, max_y = gdf_bbox_native.total_bounds

        # 2. Request data using the transformed BBOX and the native CRS
        bbox_str = f"{min_x},{min_y},{max_x},{max_y},{NATIVE_CRS}"
        params = {
            'service': 'WFS',
            'version': '1.1.0',
            'request': 'GetFeature',
            'typeName': TYPE_NAME,
            'outputFormat': 'text/xml; subtype=gml/3.2.1',
            'srsName': NATIVE_CRS,
            'BBOX': bbox_str
        }

        print(f"Requesting data from {WFS_URL} in its native CRS...")
        response = requests.get(WFS_URL, params=params, timeout=45)
        response.raise_for_status()

        if "ExceptionReport" in response.text:
            print(f"Server returned an exception report:\n{response.text[:1000]}")
            return None

        # 3. Convert the GML response to a GeoDataFrame
        print("GML data received. Converting to GeoDataFrame...")
        gml_content = io.BytesIO(response.content)
        gdf_native = geopandas.read_file(gml_content)

        if gdf_native.empty:
            print("Request successful, but no features were found in the specified area.")
            return {'type': 'FeatureCollection', 'features': []}

        # 4. Transform the resulting GeoDataFrame back to the Web CRS for display
        print(f"Reprojecting {len(gdf_native)} features back to {WEB_CRS} for display...")
        gdf_web = gdf_native.to_crs(WEB_CRS)
        
        gdf_web['id'] = gdf_web.index.astype(str)
        
        # 5. Convert the modified GeoDataFrame to GeoJSON
        geojson_data = json.loads(gdf_web.to_json())

        print(f"Processing complete. {len(geojson_data['features'])} features ready for UI.")
        return geojson_data

    except requests.exceptions.RequestException as e:
        print(f"Network error fetching data from NRW API: {e}")
        return None
    except Exception as e:
        print(f"An error occurred during the GIS workflow: {e}")
        return None