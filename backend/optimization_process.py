# backend/optimization_process.py

import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon
from backend.config import QD_CONFIG, ENCODING_CONFIG, DOMAIN_CONFIG
from backend.data_io import fetch_existing_buildings_data
from backend.encoding import ParametricEncoding
from backend.optimizer import run_qd_optimization

def create_environment(user_polygon_geojson: dict):
    if not user_polygon_geojson or not user_polygon_geojson.get('features'):
        raise ValueError("User polygon is empty or invalid.")
        
    gdf_user_poly = gpd.GeoDataFrame.from_features(user_polygon_geojson, crs="EPSG:4326")
    gdf_user_poly_native = gdf_user_poly.to_crs("EPSG:25832")
    min_x, min_y, max_x, max_y = gdf_user_poly_native.total_bounds
    
    width, height = max_x - min_x, max_y - min_y
    size = max(width, height)
    border = size * (DOMAIN_CONFIG['environment_border_size'] - 1.0) / 2.0
    
    grid_min_x, grid_min_y = min_x - border, min_y - border
    grid_max_x, grid_max_y = max_x + border, max_y + border
    
    res = ENCODING_CONFIG['xy_length']
    x = np.linspace(grid_min_x, grid_max_x, res)
    y = np.linspace(grid_min_y, grid_max_y, res)
    xv, yv = np.meshgrid(x, y)
    points = [Point(px, py) for px, py in zip(xv.flatten(), yv.flatten())]
    gdf_points = gpd.GeoDataFrame(geometry=points, crs="EPSG:25832")
    
    joined = gpd.sjoin(gdf_points, gdf_user_poly_native, how="inner", predicate="within")
    buildable_mask = np.zeros((res, res), dtype=bool)
    indices = joined.index.to_numpy()
    rows, cols = np.unravel_index(indices, (res, res))
    buildable_mask[rows, cols] = True
    
    env_3d_fixed = np.zeros((res, res, ENCODING_CONFIG['z_length']), dtype=np.int8)
    grid_poly_native = gpd.GeoSeries([Polygon.from_bounds(grid_min_x, grid_min_y, grid_max_x, grid_max_y)], crs="EPSG:25832")
    grid_poly_web = grid_poly_native.to_crs("EPSG:4326")
    b_min_lon, b_min_lat, b_max_lon, b_max_lat = grid_poly_web.total_bounds
    
    gdf_buildings_native = fetch_existing_buildings_data((b_min_lon, b_min_lat, b_max_lon, b_max_lat))
    
    if gdf_buildings_native is not None:
        cell_size_x = (grid_max_x - grid_min_x) / res
        cell_size_y = (grid_max_y - grid_min_y) / res
        for building in gdf_buildings_native.geometry:
            b_min_x, b_min_y, b_max_x, b_max_y = building.bounds
            start_col = int((b_min_x - grid_min_x) / cell_size_x)
            end_col = int((b_max_x - grid_min_x) / cell_size_x)
            start_row = int((b_min_y - grid_min_y) / cell_size_y)
            end_row = int((b_max_y - grid_min_y) / cell_size_y)
            start_row, end_row = max(0, start_row), min(res, end_row)
            start_col, end_col = max(0, start_col), min(res, end_col)
            env_3d_fixed[start_row:end_row, start_col:end_col, :3] = 1

    return {
        'buildable_mask': buildable_mask, 'env_3d_fixed': env_3d_fixed,
        'labels': DOMAIN_CONFIG['labels'], 'feat_ranges': DOMAIN_CONFIG['feat_ranges']
    }

def start_optimization(user_polygon_geojson: dict, wind_direction: int, progress_callback=None):
    progress_callback(5, "Creating environment...")
    env_config = create_environment(user_polygon_geojson)
    
    # --- THIS IS THE KEY CHANGE ---
    # Overwrite the default wind direction with the one from the GUI.
    env_config['wind_direction'] = wind_direction
    print(f"[INFO] Running optimization with wind direction: {wind_direction}°")
    
    encoding_obj = ParametricEncoding(ENCODING_CONFIG)
    progress_callback(10, "Starting optimization...")
    archive = run_qd_optimization(encoding_obj, env_config, QD_CONFIG, progress_callback)
    progress_callback(100, "Optimization complete.")
    return archive, env_config['labels'], env_config