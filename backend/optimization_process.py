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
import json


def create_environment(user_polygon_geojson: dict, selected_features: list, user_feature_ranges: dict, hard_constraints: dict = None):
    """
    Create the optimization environment with proper physical unit ranges.
    
    Args:
        user_polygon_geojson: GeoJSON of the buildable area
        selected_features: List of feature indices to optimize
        user_feature_ranges: User-defined ranges for features (in physical units)
        hard_constraints: Dict with 'max_height' (in voxels) and 'min_distance' (in meters)
    """
    if hard_constraints is None:
        hard_constraints = {}
        
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
    
    # Create two arrays: one for optimization (same size as design grid), 
    # one for visualization (expanded to show more neighborhood)
    env_3d_fixed = np.zeros((res, res, ENCODING_CONFIG['z_length']), dtype=np.int8)
    
    # Expand the area for fetching buildings for better visualization context
    neighborhood_expansion = 1.0  # Multiplier: 1.0 means 3x area (1x on each side)
    expanded_grid_side = grid_side_length * (1 + 2 * neighborhood_expansion)
    expanded_res = int(res * (1 + 2 * neighborhood_expansion))
    expanded_min_x = grid_min_x - (neighborhood_expansion * grid_side_length)
    expanded_min_y = grid_min_y - (neighborhood_expansion * grid_side_length)
    expanded_max_x = grid_max_x + (neighborhood_expansion * grid_side_length)
    expanded_max_y = grid_max_y + (neighborhood_expansion * grid_side_length)
    
    # Calculate where the design grid sits within the expanded grid
    start_idx = int(res * neighborhood_expansion)
    
    # Create expanded array for visualization
    env_3d_expanded = np.zeros((expanded_res, expanded_res, ENCODING_CONFIG['z_length']), dtype=np.int8)
    
    grid_poly_native = gpd.GeoSeries([Polygon.from_bounds(grid_min_x, grid_min_y, grid_max_x, grid_max_y)], crs="EPSG:25832")
    grid_poly_web = grid_poly_native.to_crs("EPSG:4326")
    
    # Use expanded bounds for fetching buildings
    fetch_poly_native = gpd.GeoSeries([Polygon.from_bounds(expanded_min_x, expanded_min_y, expanded_max_x, expanded_max_y)], crs="EPSG:25832")
    fetch_poly_web = fetch_poly_native.to_crs("EPSG:4326")
    b_min_lon, b_min_lat, b_max_lon, b_max_lat = fetch_poly_web.total_bounds
    
    gdf_buildings_native = fetch_existing_buildings_data((b_min_lon, b_min_lat, b_max_lon, b_max_lat))
    
    if gdf_buildings_native is not None:
        # Filter by geometry type
        geom_types = gdf_buildings_native.geometry.type
        polygon_mask = geom_types.isin(['Polygon', 'MultiPolygon'])
        gdf_polygons = gdf_buildings_native[polygon_mask].copy()

        # Filter by function to exclude non-building structures
        if 'funktion' in gdf_polygons.columns:
            # Exclude structures that are not actual buildings:
            # - "Überdachung" = canopy/roofing (like market coverings)
            # - "Tiefgarage" = underground garage (not visible above ground)
            exclude_types = ['Überdachung', 'Tiefgarage']
            
            # Keep everything except the excluded types
            function_mask = ~gdf_polygons['funktion'].isin(exclude_types)
            gdf_building_polygons = gdf_polygons[function_mask]
            
            print(f"Building filtering: {len(gdf_polygons)} total -> {len(gdf_building_polygons)} after excluding {exclude_types}")
        else:
            # Fallback if no function attribute
            perimeter = gdf_polygons.geometry.length
            area = gdf_polygons.geometry.area
            perimeter[perimeter == 0] = 1e-9
            compactness = 4 * math.pi * area / (perimeter**2)
            compact_mask = compactness > 0.1
            gdf_building_polygons = gdf_polygons[compact_mask]
            print(f"Building filtering: {len(gdf_polygons)} total -> {len(gdf_building_polygons)} after geometric filter")
        
        if not gdf_building_polygons.empty:
            # Create a mapping array to store building function for each pixel
            # We'll encode each unique function as a number
            if 'funktion' in gdf_building_polygons.columns:
                unique_functions = gdf_building_polygons['funktion'].unique()
                function_to_id = {func: idx + 1 for idx, func in enumerate(unique_functions)}
                id_to_function = {idx + 1: func for idx, func in enumerate(unique_functions)}
                
                # Rasterize with building IDs
                shapes_with_ids = [(geom, function_to_id[func]) for geom, func in 
                                   zip(gdf_building_polygons.geometry, gdf_building_polygons['funktion'])]
            else:
                shapes_with_ids = [(geom, 1) for geom in gdf_building_polygons.geometry]
                id_to_function = {1: 'Gebäude'}
            
            # Rasterize to EXPANDED grid for visualization
            cell_size_exp = expanded_grid_side / expanded_res
            transform_exp = from_origin(expanded_min_x, expanded_max_y, cell_size_exp, cell_size_exp)
            
            building_function_map_exp = features.rasterize(
                shapes=shapes_with_ids, out_shape=(expanded_res, expanded_res), transform=transform_exp,
                fill=0, dtype='uint8'
            )
            building_function_map_exp = np.flipud(building_function_map_exp)
            
            # Create boolean footprint and 3D array
            building_footprints_2d_exp = building_function_map_exp > 0
            env_3d_expanded[building_footprints_2d_exp, :3] = 1
            
            # Also rasterize to ORIGINAL grid for optimization
            cell_size = grid_side_length / res
            transform = from_origin(grid_min_x, grid_max_y, cell_size, cell_size)
            
            building_footprints_2d = features.rasterize(
                shapes=gdf_building_polygons.geometry, out_shape=(res, res), transform=transform,
                fill=0, default_value=1, dtype='uint8'
            ).astype(bool)
            building_footprints_2d = np.flipud(building_footprints_2d)
            env_3d_fixed[building_footprints_2d, :3] = 1
        else:
            building_function_map_exp = None
            id_to_function = {}

    # Initialize these in case no buildings were found
    if gdf_buildings_native is None or gdf_building_polygons.empty:
        building_function_map_exp = None
        id_to_function = {}
    
    # Clear buildings in the buildable area for both arrays
    env_3d_fixed[buildable_mask, :] = 0
    
    # Clear buildable area in expanded array - need to iterate through mask indices
    end_idx = start_idx + res
    buildable_rows, buildable_cols = np.where(buildable_mask)
    for r, c in zip(buildable_rows, buildable_cols):
        env_3d_expanded[start_idx + r, start_idx + c, :] = 0
    
    # Also clear the function map in buildable area
    if building_function_map_exp is not None:
        for r, c in zip(buildable_rows, buildable_cols):
            building_function_map_exp[start_idx + r, start_idx + c] = 0
    
    # --- Use the user-defined ranges to construct the final list of ranges for the optimizer ---
    # Extract max height from constraints (convert voxels to floors: divide by 3)
    max_height_voxels = hard_constraints.get('max_height', ENCODING_CONFIG['z_length'] * 3)
    max_height_floors = max_height_voxels // 3  # Convert to floors
    
    # Get dynamic ranges for all 8 features (now in physical units!)
    dynamic_ranges, buildable_area_m2 = _calculate_dynamic_feat_ranges(buildable_mask, max_height_floors)
    
    # Build the final ranges list: only for selected features
    final_feat_ranges = []
    final_labels = []
    
    for feature_index in selected_features:
        # Get label for this feature
        final_labels.append(DOMAIN_CONFIG['labels'][feature_index])
        
        # Check if user provided a custom range for this feature
        user_range = user_feature_ranges.get(str(feature_index))
        if user_range:
            # Use user's custom range
            final_feat_ranges.append(user_range)
        else:
            # Use dynamic range from calculations
            final_feat_ranges.append(dynamic_ranges[feature_index])
    
    grid_geojson = json.loads(grid_poly_web.to_json())

    return {
        'buildable_mask': buildable_mask, 
        'env_3d_fixed': env_3d_fixed,  # Original size for optimization
        'env_3d_expanded': env_3d_expanded,  # Expanded size for visualization
        'building_function_map': building_function_map_exp,  # 2D map of building functions
        'function_lookup': id_to_function,  # Dictionary to lookup function names
        'labels': final_labels,
        'feat_ranges': final_feat_ranges, # This now contains the user's ranges
        'buildable_area_in_sq_meters': buildable_area_m2,
        'selected_features': selected_features,
        'grid_geojson': grid_geojson,
        'grid_bounds_native': (grid_min_x, grid_min_y, grid_max_x, grid_max_y),  # Design area bounds
        'expanded_bounds_native': (expanded_min_x, expanded_min_y, expanded_max_x, expanded_max_y),  # Expanded visualization bounds
        'design_offset': (start_idx, start_idx),  # Where design grid sits within expanded grid
    }


def _calculate_dynamic_feat_ranges(buildable_mask: np.ndarray, max_height_floors: int = None):
    """
    Calculate dynamic feature ranges in PHYSICAL UNITS based on site properties.
    
    Args:
        buildable_mask: Boolean array of buildable pixels
        max_height_floors: Maximum building height in floors (from hard constraints)
    
    Returns:
        Tuple of (ranges_list, buildable_area_m2)
        Ranges are in physical units: [m²], [m], [m], [count], [m], [m²], [0-1], [0-1]
    """
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    z_len = ENCODING_CONFIG['z_length']
    meters_per_floor = 3.0
    
    # Use constraint-based max height if provided, otherwise use default
    if max_height_floors is None:
        max_height_floors = z_len
    
    buildable_pixels = np.sum(buildable_mask)
    if buildable_pixels == 0:
        return DOMAIN_CONFIG['feat_ranges'], 0.0
        
    buildable_area_m2 = buildable_pixels * (pixel_size ** 2)
    grid_res = buildable_mask.shape[0]
    max_dist_pixels = np.sqrt(2) * grid_res  # Diagonal distance
    max_dist_meters = max_dist_pixels * pixel_size
    
    # Maximum possible floor area depends on max height constraint
    max_possible_floor_area_m2 = buildable_area_m2 * max_height_floors
    
    new_ranges = [
        [0.0, buildable_area_m2],                      # 0: Built Area (m²)
        [0.0, max_height_floors * meters_per_floor],   # 1: Avg Height (m)
        [0.0, max_height_floors * meters_per_floor / 2], # 2: Height Variability (m)
        [0.0, ENCODING_CONFIG['max_num_buildings']],   # 3: Number of Buildings (count)
        [0.0, max_dist_meters],                        # 4: Avg Distance (m)
        [0.0, max_possible_floor_area_m2],             # 5: Gross Floor Area (m²)
        [0.0, 1.0],                                    # 6: Building Mass X (normalized)
        [0.0, 1.0],                                    # 7: Building Mass Y (normalized)
    ]
    return new_ranges, buildable_area_m2


def start_optimization(user_polygon_geojson: dict, wind_direction: int, selected_features: list, user_feature_ranges: dict, hard_constraints: dict, qd_hyperparams: dict = None, progress_callback=None):
    progress_callback(5, "Creating environment...")
    # Pass hard_constraints to create_environment so it can calculate proper ranges
    env_config = create_environment(user_polygon_geojson, selected_features, user_feature_ranges, hard_constraints)
    env_config['wind_direction'] = wind_direction
    env_config['hard_constraints'] = hard_constraints
    
    # Merge user-defined QD hyperparameters with defaults
    qd_config = QD_CONFIG.copy()
    if qd_hyperparams:
        qd_config.update(qd_hyperparams)
    
    encoding_obj = ParametricEncoding(ENCODING_CONFIG)
    sample_genome = np.random.randn(encoding_obj.get_dimension())
    create_debug_plots(env_config, sample_genome, encoding_obj)
    progress_callback(10, "Starting optimization...")
    archive = run_qd_optimization(
        encoding_obj, env_config, qd_config, progress_callback)
    progress_callback(100, "Optimization complete.")
    return archive, env_config['labels'], env_config
