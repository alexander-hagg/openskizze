#
# backend/optimization_process.py (Final Corrected Version)
#
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon
from backend.config import QD_CONFIG, ENCODING_CONFIG, DOMAIN_CONFIG
from backend.data_io import fetch_existing_buildings_data
from backend.encoding import ParametricEncoding
from backend.optimizer import run_qd_optimization
from backend.debugging_plots import create_debug_plots
import math

def create_environment(user_polygon_geojson: dict, selected_features: list):
    # ... (code for creating buildable_mask and env_3d_fixed is unchanged) ...
    if not user_polygon_geojson or not user_polygon_geojson.get('features'):
        raise ValueError("User polygon is empty or invalid.")
    gdf_user_poly = gpd.GeoDataFrame.from_features(user_polygon_geojson, crs="EPSG:4326")
    gdf_user_poly_native = gdf_user_poly.to_crs("EPSG:25832")
    min_x, min_y, max_x, max_y = gdf_user_poly_native.total_bounds
    width = max_x-min_x; height=max_y-min_y; square_size=max(width,height)
    center_x, center_y = (min_x+max_x)/2, (min_y+max_y)/2
    square_min_x, square_min_y = center_x-square_size/2, center_y-square_size/2
    border = square_size * (DOMAIN_CONFIG['environment_border_size'] - 1.0)/2.0
    grid_min_x, grid_min_y = square_min_x-border, square_min_y-border
    grid_side_length = square_size + (2*border)
    grid_max_x, grid_max_y = grid_min_x+grid_side_length, grid_min_y+grid_side_length
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    res = math.ceil(grid_side_length/pixel_size)
    ENCODING_CONFIG['xy_length'] = res
    x = np.linspace(grid_min_x, grid_max_x, res); y = np.linspace(grid_min_y, grid_max_y, res)
    xv, yv = np.meshgrid(x,y)
    points = [Point(px,py) for px,py in zip(xv.flatten(),yv.flatten())]
    gdf_points=gpd.GeoDataFrame(geometry=points,crs="EPSG:25832")
    joined = gpd.sjoin(gdf_points, gdf_user_poly_native, how="inner", predicate="within")
    buildable_mask = np.zeros((res,res), dtype=bool)
    indices = joined.index.to_numpy()
    rows, cols = np.unravel_index(indices, (res,res))
    buildable_mask[rows, cols] = True
    env_3d_fixed = np.zeros((res,res,ENCODING_CONFIG['z_length']),dtype=np.int8)
    grid_poly_native=gpd.GeoSeries([Polygon.from_bounds(grid_min_x,grid_min_y,grid_max_x,grid_max_y)], crs="EPSG:25832")
    grid_poly_web = grid_poly_native.to_crs("EPSG:4326")
    b_min_lon, b_min_lat, b_max_lon, b_max_lat = grid_poly_web.total_bounds
    gdf_buildings_native = fetch_existing_buildings_data((b_min_lon,b_min_lat,b_max_lon,b_max_lat))
    if gdf_buildings_native is not None:
        cell_size = grid_side_length/res
        for building in gdf_buildings_native.geometry:
            b_min_x,b_min_y,b_max_x,b_max_y = building.bounds
            start_col,end_col = int((b_min_x-grid_min_x)/cell_size),int((b_max_x-grid_min_x)/cell_size)
            start_row,end_row = int((b_min_y-grid_min_y)/cell_size),int((b_max_y-grid_min_y)/cell_size)
            start_row,end_row=max(0,start_row),min(res,end_row)
            start_col,end_col=max(0,start_col),min(res,end_col)
            env_3d_fixed[start_row:end_row,start_col:end_col,:3]=1
    env_3d_fixed[buildable_mask,:]=0
    
    # --- DYNAMIC CONFIGURATION BASED ON USER SELECTION ---
    dynamic_ranges, buildable_area_m2 = _calculate_dynamic_feat_ranges(buildable_mask)
    
    # 1. Filter the labels based on the selected indices
    final_labels = [DOMAIN_CONFIG['labels'][i] for i in selected_features]
    # 2. Filter the feature ranges based on the selected indices
    final_feat_ranges = [dynamic_ranges[i] for i in selected_features]

    return {
        'buildable_mask': buildable_mask, 
        'env_3d_fixed': env_3d_fixed,
        'labels': final_labels, # Use the filtered list
        'feat_ranges': final_feat_ranges, # Use the filtered list
        'buildable_area_in_sq_meters': buildable_area_m2,
        'selected_features': selected_features # Pass this down to the evaluator
    }

def _calculate_dynamic_feat_ranges(buildable_mask: np.ndarray):
    # This function is unchanged
    pixel_size=DOMAIN_CONFIG['pixel_size_in_meters']; z_len=ENCODING_CONFIG['z_length']
    buildable_pixels=np.sum(buildable_mask)
    if buildable_pixels==0: return DOMAIN_CONFIG['feat_ranges'],0.0
    buildable_area_sq_meters = buildable_pixels * (pixel_size**2)
    grid_res=buildable_mask.shape[0]
    new_ranges=[[0.0,1.0],[0.0,z_len],[0.0,z_len/2],[0.0,ENCODING_CONFIG['max_num_buildings']],[0.0,1.0],[0.0,1.0],[0.0,1.0],[0.0,1.0],]
    return new_ranges, buildable_area_sq_meters

def start_optimization(user_polygon_geojson: dict, wind_direction: int, selected_features: list, progress_callback=None):
    progress_callback(5, "Creating environment...")
    env_config = create_environment(user_polygon_geojson, selected_features)
    env_config['wind_direction'] = wind_direction
    encoding_obj = ParametricEncoding(ENCODING_CONFIG)
    
    # Create debug plots only if running in a non-production environment
    # sample_genome = np.random.randn(encoding_obj.get_dimension())
    # create_debug_plots(env_config, sample_genome, encoding_obj)
    
    progress_callback(10, "Starting optimization...")
    archive = run_qd_optimization(encoding_obj, env_config, QD_CONFIG, progress_callback)
    
    progress_callback(100, "Optimization complete.")
    return archive, env_config['labels'], env_config