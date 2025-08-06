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

def create_environment(user_polygon_geojson: dict):
    if not user_polygon_geojson or not user_polygon_geojson.get('features'):
        raise ValueError("User polygon is empty or invalid.")
        
    gdf_user_poly = gpd.GeoDataFrame.from_features(user_polygon_geojson, crs="EPSG:4326")
    gdf_user_poly_native = gdf_user_poly.to_crs("EPSG:25832")
    min_x, min_y, max_x, max_y = gdf_user_poly_native.total_bounds
    
    # --- THE CRITICAL FIX FOR SCALING AND ROTATION ---
    # 1. Determine the real-world size of the bounding box.
    width = max_x - min_x
    height = max_y - min_y
    
    # 2. Find the largest dimension to define the size of a square container.
    square_size = max(width, height)
    
    # 3. Center the original box inside this conceptual square.
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    square_min_x = center_x - square_size / 2
    square_min_y = center_y - square_size / 2
    
    # 4. Add the border to the SQUARE.
    border = square_size * (DOMAIN_CONFIG['environment_border_size'] - 1.0) / 2.0
    grid_min_x = square_min_x - border
    grid_min_y = square_min_y - border
    grid_side_length = square_size + (2 * border)
    grid_max_x = grid_min_x + grid_side_length
    grid_max_y = grid_min_y + grid_side_length
    
    # 5. Dynamically calculate the grid resolution to enforce a 3m pixel size.
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    res = math.ceil(grid_side_length / pixel_size)
    print(f"[DEBUG] Calculated resolution: {res}x{res} pixels for a grid size of {grid_side_length:.2f}m with pixel size {pixel_size:.2f}m.")
    print(f"[DEBUG] old ENCODING_CONFIG['xy_length']: {ENCODING_CONFIG['xy_length']}, new res: {res}")
    ENCODING_CONFIG['xy_length'] = res # Update config for other modules
    
    print(f"[DEBUG] Real-world grid size: {grid_side_length:.2f}m. Pixel size: {pixel_size}m. Calculated Resolution: {res}x{res} pixels.")

    # 6. Create the grid based on these final square dimensions.
    x = np.linspace(grid_min_x, grid_max_x, res)
    y = np.linspace(grid_min_y, grid_max_y, res)
    # --- END OF FIX ---
    
    xv, yv = np.meshgrid(x, y)
    points = [Point(px, py) for px, py in zip(xv.flatten(), yv.flatten())]
    gdf_points = gpd.GeoDataFrame(geometry=points, crs="EPSG:25832")
    
    joined = gpd.sjoin(gdf_points, gdf_user_poly_native, how="inner", predicate="within")
    buildable_mask = np.zeros((res, res), dtype=bool)
    indices = joined.index.to_numpy()
    rows, cols = np.unravel_index(indices, (res, res))
    
    # Create the mask with correct (row, col) -> (y, x) mapping. No transpose needed.
    buildable_mask[rows, cols] = True
    
    print(f"[DEBUG] Buildable Mask created. Shape: {buildable_mask.shape}. Buildable cells: {np.sum(buildable_mask)}")
    
    env_3d_fixed = np.zeros((res, res, ENCODING_CONFIG['z_length']), dtype=np.int8)
    grid_poly_native = gpd.GeoSeries([Polygon.from_bounds(grid_min_x, grid_min_y, grid_max_x, grid_max_y)], crs="EPSG:25832")
    grid_poly_web = grid_poly_native.to_crs("EPSG:4326")
    b_min_lon, b_min_lat, b_max_lon, b_max_lat = grid_poly_web.total_bounds
    
    gdf_buildings_native = fetch_existing_buildings_data((b_min_lon, b_min_lat, b_max_lon, b_max_lat))
    
    if gdf_buildings_native is not None:
        cell_size = grid_side_length / res # Cells are now square
        for building in gdf_buildings_native.geometry:
            b_min_x, b_min_y, b_max_x, b_max_y = building.bounds
            start_col = int((b_min_x - grid_min_x) / cell_size)
            end_col = int((b_max_x - grid_min_x) / cell_size)
            start_row = int((b_min_y - grid_min_y) / cell_size)
            end_row = int((b_max_y - grid_min_y) / cell_size)
            
            start_row, end_row = max(0, start_row), min(res, end_row)
            start_col, end_col = max(0, start_col), min(res, end_col)

            env_3d_fixed[start_row:end_row, start_col:end_col, :3] = 1

    print(f"[DEBUG] Fixed 3D Environment created. Shape: {env_3d_fixed.shape}. Occupied voxels: {np.sum(env_3d_fixed)}")

    dynamic_ranges, buildable_area_m2 = _calculate_dynamic_feat_ranges(buildable_mask)

    return {
        'buildable_mask': buildable_mask, 
        'env_3d_fixed': env_3d_fixed,
        'labels': DOMAIN_CONFIG['labels'],
        'feat_ranges': dynamic_ranges,
        'buildable_area_in_sq_meters': buildable_area_m2
    }

def _calculate_dynamic_feat_ranges(buildable_mask: np.ndarray):
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    # Get the dynamically calculated resolution
    grid_res = buildable_mask.shape[0]
    z_len = ENCODING_CONFIG['z_length']
    buildable_pixels = np.sum(buildable_mask)
    if buildable_pixels == 0:
        return DOMAIN_CONFIG['feat_ranges'], 0.0

    buildable_area_sq_meters = buildable_pixels * (pixel_size ** 2)
    new_ranges = [
        [0.0, 1.0], [0.0, z_len], [0.0, z_len / 2],
        [0.0, ENCODING_CONFIG['max_num_buildings']],
        [0.0, grid_res * 1.414], [0.0, min(z_len, 5.0)],
        [0.0, grid_res], [0.0, grid_res],
    ]
    print(f"[DEBUG] Dynamic feature ranges calculated. Buildable area: {buildable_area_sq_meters:.2f} m².")
    return new_ranges, buildable_area_sq_meters

def start_optimization(user_polygon_geojson: dict, wind_direction: int, progress_callback=None):
    progress_callback(5, "Creating environment...")
    env_config = create_environment(user_polygon_geojson)
    env_config['wind_direction'] = wind_direction
    
    # The ENCODING_CONFIG was updated dynamically inside create_environment
    encoding_obj = ParametricEncoding(ENCODING_CONFIG)
    
    sample_genome = np.random.randn(encoding_obj.get_dimension())
    create_debug_plots(env_config, sample_genome, encoding_obj)
    
    progress_callback(10, "Starting optimization...")
    archive = run_qd_optimization(encoding_obj, env_config, QD_CONFIG, progress_callback)
    
    progress_callback(100, "Optimization complete.")
    return archive, env_config['labels'], env_config