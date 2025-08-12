#
# backend/optimization_process.py (Final Corrected Version with Shape Filtering and Rasterio)
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
from rasterio import features
from rasterio.transform import from_origin

def create_environment(user_polygon_geojson: dict, selected_features: list):
    if not user_polygon_geojson or not user_polygon_geojson.get('features'):
        raise ValueError("User polygon is empty or invalid.")
        
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
    grid_min_x = square_min_x - border
    grid_min_y = square_min_y - border
    grid_side_length = square_size + (2 * border)
    grid_max_x = grid_min_x + grid_side_length
    grid_max_y = grid_min_y + grid_side_length
    
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    res = math.ceil(grid_side_length / pixel_size)
    ENCODING_CONFIG['xy_length'] = res
    
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
        # --- THE CRITICAL FIX IS HERE ---
        # 1. Filter out non-polygon geometries.
        geom_types = gdf_buildings_native.geometry.type
        polygon_mask = geom_types.isin(['Polygon', 'MultiPolygon'])
        gdf_polygons = gdf_buildings_native[polygon_mask].copy()

        # 2. Filter out long, thin, non-building-like polygons using a compactness ratio.
        # Polsoy-Popper ratio: 4 * pi * area / perimeter^2. A circle is 1.0, a line is ~0.
        # We keep shapes that are at least somewhat "blobby".
        perimeter = gdf_polygons.geometry.length
        area = gdf_polygons.geometry.area
        # Avoid division by zero for invalid geometries
        perimeter[perimeter == 0] = 1e-9
        compactness = 4 * math.pi * area / (perimeter**2)
        compact_mask = compactness > 0.1 # Threshold to filter out line-like shapes
        gdf_building_polygons = gdf_polygons[compact_mask]
        
        print(f"[DEBUG] Filtered buildings: Kept {len(gdf_building_polygons)} compact polygons out of {len(gdf_buildings_native)} total geometries.")

        # 3. Accurately rasterize the *actual shapes* of the filtered buildings.
        if not gdf_building_polygons.empty:
            cell_size = grid_side_length / res
            # Create a transform for rasterio (origin is top-left)
            transform = from_origin(grid_min_x, grid_max_y, cell_size, cell_size)
            
            # Burn the geometries into a 2D array.
            building_footprints_2d = features.rasterize(
                shapes=gdf_building_polygons.geometry,
                out_shape=(res, res),
                transform=transform,
                fill=0,
                default_value=1,
                dtype='uint8'
            ).astype(bool)
            building_footprints_2d = np.flipud(building_footprints_2d)
            
            # Assume a fixed height for existing buildings and create the 3D environment
            env_3d_fixed[building_footprints_2d, :3] = 1

    env_3d_fixed[buildable_mask, :] = 0
    print(f"[DEBUG] Fixed 3D Environment created. Occupied voxels (context only): {np.sum(env_3d_fixed)}")

    dynamic_ranges, buildable_area_m2 = _calculate_dynamic_feat_ranges(buildable_mask)
    final_labels = [DOMAIN_CONFIG['labels'][i] for i in selected_features]
    final_feat_ranges = [dynamic_ranges[i] for i in selected_features]

    return {
        'buildable_mask': buildable_mask, 
        'env_3d_fixed': env_3d_fixed,
        'labels': final_labels,
        'feat_ranges': final_feat_ranges,
        'buildable_area_in_sq_meters': buildable_area_m2,
        'selected_features': selected_features
    }

def _calculate_dynamic_feat_ranges(buildable_mask: np.ndarray) -> (list, float):
    # ... (this function is unchanged) ...
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    z_len = ENCODING_CONFIG['z_length']
    buildable_pixels = np.sum(buildable_mask)
    if buildable_pixels == 0: return DOMAIN_CONFIG['feat_ranges'], 0.0
    buildable_area_sq_meters = buildable_pixels * (pixel_size ** 2)
    grid_res = buildable_mask.shape[0]
    new_ranges = [
        [0.0, 1.0], [0.0, z_len], [0.0, z_len / 2],
        [0.0, ENCODING_CONFIG['max_num_buildings']],
        [0.0, 1.0], [0.0, 1.0], [0.0, 1.0], [0.0, 1.0],
    ]
    return new_ranges, buildable_area_sq_meters

def start_optimization(user_polygon_geojson: dict, wind_direction: int, selected_features: list, progress_callback=None):
    # ... (this function is unchanged) ...
    progress_callback(5, "Creating environment...")
    env_config = create_environment(user_polygon_geojson, selected_features)
    env_config['wind_direction'] = wind_direction
    encoding_obj = ParametricEncoding(ENCODING_CONFIG)
    sample_genome = np.random.randn(encoding_obj.get_dimension())
    create_debug_plots(env_config, sample_genome, encoding_obj)
    progress_callback(10, "Starting optimization...")
    archive = run_qd_optimization(encoding_obj, env_config, QD_CONFIG, progress_callback)
    progress_callback(100, "Optimization complete.")
    return archive, env_config['labels'], env_config