#
# backend/optimization_process.py (Final Corrected Version with Shape Filtering and Rasterio)
#
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
from scipy.ndimage import rotate
from backend.config import QD_CONFIG, ENCODING_CONFIG, DOMAIN_CONFIG, SURROGATE_CONFIG
from backend.data_io import fetch_existing_buildings_data
from backend.encoding import ParametricEncoding
from backend.optimizer import run_qd_optimization
from backend.debugging_plots import create_debug_plots
import math
from rasterio import features
from rasterio.transform import from_origin
import json


def create_environment(user_polygon_geojson: dict, selected_features: list, user_feature_ranges: dict, hard_constraints: dict = None, cached_building_data: dict = None, feature_set: str = 'consolidated', model_type: str = 'original', ucb_lambda: float = 1.0, grid_params: dict = None):
    """
    Create the optimization environment with proper physical unit ranges.
    
    Args:
        user_polygon_geojson: GeoJSON of the buildable area
        selected_features: List of feature indices to optimize
        user_feature_ranges: User-defined ranges for features (in physical units)
        hard_constraints: Dict with 'max_height' (in voxels) and 'min_distance' (in meters)
        cached_building_data: Optional pre-fetched building data from Step 1 (for performance)
        feature_set: 'consolidated' (default)
        grid_params: Pre-calculated grid parameters from step 1 (to avoid recalculation differences)
        model_type: 'original', 'svgp', 'unet', or 'hybrid'
        ucb_lambda: UCB exploration parameter for SVGP/Hybrid models
    """
    if hard_constraints is None:
        hard_constraints = {}
        
    if not user_polygon_geojson or not user_polygon_geojson.get('features'):
        raise ValueError("User polygon is empty or invalid.")
        
    gdf_user_poly = gpd.GeoDataFrame.from_features(user_polygon_geojson, crs="EPSG:4326")
    gdf_user_poly_native = gdf_user_poly.to_crs("EPSG:25832")
    min_x, min_y, max_x, max_y = gdf_user_poly_native.total_bounds
    
    # Use pre-calculated grid_params if available (from step 1), otherwise calculate
    if grid_params and 'xy_length' in grid_params:
        res = grid_params['xy_length']
        grid_side_length = grid_params['grid_side_length']
        pixel_size = grid_params['pixel_size']
        print(f"[create_environment] Using pre-calculated grid: {res} bins ({grid_side_length:.1f}m)")
    else:
        width = max_x - min_x
        height = max_y - min_y
        square_size = max(width, height)
        border = square_size * (DOMAIN_CONFIG['environment_border_size'] - 1.0) / 2.0
        grid_side_length = square_size + (2 * border)
        pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
        res = math.ceil(grid_side_length / pixel_size)
        print(f"[create_environment] Calculated grid: {res} bins ({grid_side_length:.1f}m)")
    
    ENCODING_CONFIG['xy_length'] = res
    
    # Calculate grid bounds for buildable mask
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
    grid_max_x = grid_min_x + grid_side_length
    grid_max_y = grid_min_y + grid_side_length
    
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
    # z-axis size in meters (each voxel = 1 meter)
    max_z_meters = int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])
    env_3d_fixed = np.zeros((res, res, max_z_meters), dtype=np.int8)
    
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
    env_3d_expanded = np.zeros((expanded_res, expanded_res, max_z_meters), dtype=np.int8)
    
    grid_poly_native = gpd.GeoSeries([Polygon.from_bounds(grid_min_x, grid_min_y, grid_max_x, grid_max_y)], crs="EPSG:25832")
    grid_poly_web = grid_poly_native.to_crs("EPSG:4326")
    
    # ============================================================================
    # Check if we have cached building data from Step 1
    # ============================================================================
    building_function_map_exp = None
    id_to_function = {}
    gdf_building_polygons = None
    
    if cached_building_data is not None:
        print("[create_environment] ✓ Using cached building data from Step 1")
        
        # Extract cached data
        cached_env_3d_expanded = cached_building_data.get('env_3d_expanded')
        building_function_map_exp = cached_building_data.get('building_function_map')
        id_to_function = cached_building_data.get('function_lookup', {})
        gdf_building_polygons = cached_building_data.get('gdf_buildings_filtered')
        
        # Validate that cached data matches our grid resolution
        if cached_env_3d_expanded is None or cached_env_3d_expanded.shape[0] != expanded_res or cached_env_3d_expanded.shape[1] != expanded_res:
            print(f"[create_environment] ⚠ Cached data resolution mismatch or invalid")
            print("[create_environment] Falling back to fetching buildings from API")
            cached_building_data = None  # Invalidate cache and fetch fresh data
        else:
            # Cache is valid, use it
            env_3d_expanded = cached_env_3d_expanded
            print(f"[create_environment] ✓ Using cached building data with {len(gdf_building_polygons) if gdf_building_polygons is not None else 0} buildings")
    
    # ============================================================================
    # If no cache or cache invalid, fetch buildings from NRW API
    # ============================================================================
    if cached_building_data is None:
        print("[create_environment] Fetching building data from NRW API...")
        
        # Use expanded bounds for fetching buildings
        fetch_poly_native = gpd.GeoSeries([Polygon.from_bounds(expanded_min_x, expanded_min_y, expanded_max_x, expanded_max_y)], crs="EPSG:25832")
        fetch_poly_web = fetch_poly_native.to_crs("EPSG:4326")
        b_min_lon, b_min_lat, b_max_lon, b_max_lat = fetch_poly_web.total_bounds
        
        gdf_buildings_native = fetch_existing_buildings_data((b_min_lon, b_min_lat, b_max_lon, b_max_lat))
        
        # Process the fetched building data
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
                # Extract real building heights from NRW data
                # CRITICAL: Keep everything in METERS for consistency
                # Try 'hoehe' (height in meters) or 'geschosszahl' (number of floors)
                if 'hoehe' in gdf_building_polygons.columns:
                    # Height in meters - keep as is
                    heights_meters = gdf_building_polygons['hoehe'].fillna(9.0)  # Default 9m
                elif 'geschosszahl' in gdf_building_polygons.columns:
                    # Convert floors to meters (1 floor = 3m)
                    heights_meters = gdf_building_polygons['geschosszahl'].fillna(3.0) * 3.0
                else:
                    # Fallback: assume 9 meters
                    heights_meters = pd.Series([9.0] * len(gdf_building_polygons))
                
                # Clip heights to reasonable range (3-90 meters)
                heights_meters = heights_meters.clip(3.0, 90.0)
                
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
                
                # Rasterize heights to EXPANDED grid - create 2D heightmap in METERS
                shapes_with_heights = [(geom, height) for geom, height in 
                                       zip(gdf_building_polygons.geometry, heights_meters)]
                building_heights_2d_exp = features.rasterize(
                    shapes=shapes_with_heights, out_shape=(expanded_res, expanded_res), transform=transform_exp,
                    fill=0, dtype='float32'
                )
                building_heights_2d_exp = np.flipud(building_heights_2d_exp)
                
                # Create 3D array with actual heights (each voxel = 1 METER)
                # Calculate how many voxel layers needed for each position
                default_max_height_meters = int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])
                max_height_meters = int(np.ceil(building_heights_2d_exp.max())) if building_heights_2d_exp.max() > 0 else default_max_height_meters
                max_height_meters = max(max_height_meters, default_max_height_meters)  # At least default max height
                
                # Resize env_3d_expanded if needed to accommodate real heights
                if env_3d_expanded.shape[2] < max_height_meters:
                    new_env_3d_expanded = np.zeros((expanded_res, expanded_res, max_height_meters), dtype=np.int8)
                    new_env_3d_expanded[:, :, :env_3d_expanded.shape[2]] = env_3d_expanded
                    env_3d_expanded = new_env_3d_expanded
                
                # Fill voxels up to building height (in meters)
                for r in range(expanded_res):
                    for c in range(expanded_res):
                        height_meters = building_heights_2d_exp[r, c]
                        if height_meters > 0:
                            height_voxels = int(np.round(height_meters))  # Round to nearest meter
                            env_3d_expanded[r, c, :min(height_voxels, env_3d_expanded.shape[2])] = 1
                
                # Also rasterize to ORIGINAL grid for optimization
                cell_size = grid_side_length / res
                transform = from_origin(grid_min_x, grid_max_y, cell_size, cell_size)
                
                # Rasterize heights to original grid (in METERS)
                building_heights_2d = features.rasterize(
                    shapes=shapes_with_heights, out_shape=(res, res), transform=transform,
                    fill=0, dtype='float32'
                )
                building_heights_2d = np.flipud(building_heights_2d)
                
                # Resize env_3d_fixed if needed
                if env_3d_fixed.shape[2] < max_height_meters:
                    new_env_3d_fixed = np.zeros((res, res, max_height_meters), dtype=np.int8)
                    new_env_3d_fixed[:, :, :env_3d_fixed.shape[2]] = env_3d_fixed
                    env_3d_fixed = new_env_3d_fixed
                
                # Fill voxels up to building height for optimization grid (in floors)
                for r in range(res):
                    for c in range(res):
                        height_floors = building_heights_2d[r, c]
                        if height_floors > 0:
                            height_voxels = int(np.round(height_floors))
                            env_3d_fixed[r, c, :min(height_voxels, env_3d_fixed.shape[2])] = 1
            else:
                building_function_map_exp = None
                id_to_function = {}

            # Initialize these in case no buildings were found
            if gdf_buildings_native is None or gdf_building_polygons.empty:
                building_function_map_exp = None
                id_to_function = {}
    
    # ============================================================================
    # Create env_3d_fixed from expanded array (extract design area)
    # This is needed whether we used cache or fetched fresh data
    # ============================================================================
    # Extract the design area from the expanded array
    end_idx = start_idx + res
    env_3d_fixed_from_expanded = env_3d_expanded[start_idx:end_idx, start_idx:end_idx, :]
    
    # Ensure env_3d_fixed has the right size
    if env_3d_fixed.shape[2] < env_3d_fixed_from_expanded.shape[2]:
        env_3d_fixed = np.zeros((res, res, env_3d_fixed_from_expanded.shape[2]), dtype=np.int8)
    
    # Copy the extracted data
    env_3d_fixed[:, :, :env_3d_fixed_from_expanded.shape[2]] = env_3d_fixed_from_expanded
    
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
    # Extract constraints (already in meters)
    default_max_height_meters = int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])
    max_height_meters = hard_constraints.get('max_height', default_max_height_meters)
    min_distance_meters = hard_constraints.get('min_distance', 0.0)
    
    # Get dynamic ranges for all 8 features (now in physical units, respecting hard constraints!)
    dynamic_ranges, buildable_area_m2 = _calculate_dynamic_feat_ranges(buildable_mask, max_height_meters, min_distance_meters, feature_set)
    
    # Build the final ranges list: only for selected features
    final_feat_ranges = []
    final_labels = []
    
    # Import translation helper
    from backend.translation import T
    
    for feature_index in selected_features:
        # Get label for this feature based on feature set
        label_key = f'MEASURE_{feature_index}'
        final_labels.append(T['DE'][label_key])
        
        # Check if user provided a custom range for this feature
        user_range = user_feature_ranges.get(str(feature_index))
        if user_range:
            # Use user's custom range
            final_feat_ranges.append(user_range)
        else:
            # Use dynamic range from calculations
            final_feat_ranges.append(dynamic_ranges[feature_index])
    
    grid_geojson = json.loads(grid_poly_web.to_json())
    
    # Calculate and log adaptive phenotype configuration
    from backend.config import calculate_adaptive_phenotype_config
    
    phenotype_config = calculate_adaptive_phenotype_config(
        buildable_mask=buildable_mask,
        buildable_area_m2=buildable_area_m2,
        grid_res=res
    )
    
    # === SURROGATE MODEL SETUP ===
    use_surrogate = model_type != 'original'
    surrogate_wrapper = None
    
    if use_surrogate:
        from backend.surrogate_evaluator import create_surrogate_wrapper
        
        # Calculate parcel size in bins
        parcel_size_bins = res  # res is already calculated above
        
        surrogate_wrapper = create_surrogate_wrapper(
            model_type=model_type,
            parcel_size_bins=parcel_size_bins,
            ucb_lambda=ucb_lambda
        )
        
        if surrogate_wrapper is None:
            print(f"[create_environment] WARNING: Could not create surrogate wrapper for {model_type}")
            print("[create_environment] Falling back to original evaluation")
            use_surrogate = False
    
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
        'feature_set': feature_set,  # NEW: Store which feature set is being used
        'grid_geojson': grid_geojson,
        'grid_bounds_native': (grid_min_x, grid_min_y, grid_max_x, grid_max_y),  # Design area bounds
        'expanded_bounds_native': (expanded_min_x, expanded_min_y, expanded_max_x, expanded_max_y),  # Expanded visualization bounds
        'design_offset': (start_idx, start_idx),  # Where design grid sits within expanded grid
        'phenotype_config': phenotype_config,  # NEW: Adaptive phenotype parameters
        'use_surrogate': use_surrogate,  # NEW: Whether using surrogate model
        'model_type': model_type,  # NEW: Model type ('original', 'svgp', 'unet', 'hybrid')
        'ucb_lambda': ucb_lambda,  # NEW: UCB exploration parameter
        'surrogate_wrapper': surrogate_wrapper,  # NEW: Surrogate evaluator wrapper instance
    }


def _calculate_dynamic_feat_ranges(buildable_mask: np.ndarray, max_height_meters: int = None, min_distance_meters: float = None, feature_set: str = 'consolidated'):
    """
    Calculate dynamic feature ranges in PHYSICAL UNITS based on site properties and hard constraints.
    
    Args:
        buildable_mask: Boolean array of buildable pixels
        max_height_meters: Maximum building height in meters (from hard constraints)
        min_distance_meters: Minimum distance between buildings in meters (from hard constraints)
        feature_set: 'consolidated' (default)
    
    Returns:
        Tuple of (ranges_list, buildable_area_m2)
    """
    from backend.units import calculate_dynamic_ranges_physical
    
    # Use the centralized logic in units.py
    ranges = calculate_dynamic_ranges_physical(buildable_mask, max_height_meters, min_distance_meters)
    
    # Calculate buildable area for return value
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    buildable_pixels = np.sum(buildable_mask)
    buildable_area_m2 = buildable_pixels * (pixel_size ** 2)
    
    return ranges, buildable_area_m2


def start_optimization(
    user_polygon_geojson: dict, 
    wind_direction: int, 
    selected_features: list, 
    user_feature_ranges: dict, 
    hard_constraints: dict, 
    qd_hyperparams: dict = None, 
    objective_function: str = 'street_canyon', 
    cached_building_data: dict = None, 
    feature_set: str = 'consolidated', 
    progress_callback=None,
    model_type: str = 'street_canyon',
    ucb_lambda: float = 1.0,
    grid_params: dict = None
):
    progress_callback(5, "Creating environment...")
    
    # Map unified model_type to objective_function and surrogate settings
    # Geometric methods: simple_porosity, street_canyon
    # ML methods: unet (uses street_canyon objective, but via surrogate)
    use_surrogate = model_type == 'unet'
    
    if model_type in ['simple_porosity', 'street_canyon']:
        # Geometric methods: use specified objective directly
        actual_objective = model_type
    elif model_type == 'unet':
        # U-Net: trained on street_canyon, use that as base objective
        actual_objective = 'street_canyon'
    else:
        # Legacy model types (svgp, hybrid) — fall back to geometric
        actual_objective = 'street_canyon'
        use_surrogate = False
    
    # Pass hard_constraints, cached_building_data, feature_set, and grid_params to create_environment
    env_config = create_environment(
        user_polygon_geojson, 
        selected_features, 
        user_feature_ranges, 
        hard_constraints, 
        cached_building_data, 
        feature_set,
        model_type=model_type,
        ucb_lambda=ucb_lambda,
        grid_params=grid_params
    )
    env_config['wind_direction'] = wind_direction
    env_config['hard_constraints'] = hard_constraints
    env_config['objective_function'] = actual_objective
    
    # --- PRE-ROTATE ENVIRONMENT HEIGHTMAP (ONCE) ---
    # Extract 2D heightmap from 3D environment (max height at each position)
    env_heightmap_2d = np.max(env_config['env_3d_fixed'], axis=2)
    # Rotate to wind direction once (instead of rotating 80,000 times during optimization)
    rotation_angle = (wind_direction + 90) % 360
    env_heightmap_2d_rotated = rotate(env_heightmap_2d, angle=rotation_angle, reshape=False, order=0)
    env_config['env_heightmap_2d_rotated'] = env_heightmap_2d_rotated
    
    # Safety checks before optimization
    buildable_area_m2 = env_config['buildable_area_in_sq_meters']
    buildable_mask = env_config['buildable_mask']
    buildable_pixels = np.sum(buildable_mask)
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    
    # Check 1: Minimum buildable area
    if buildable_area_m2 < 50:
        raise ValueError(f"Buildable area is too small ({buildable_area_m2:.1f} m²). Minimum required: 50 m². Please select a larger parcel.")
    
    # Check 2: Minimum buildable pixels
    if buildable_pixels < 10:
        raise ValueError(f"Too few buildable pixels ({buildable_pixels}). Minimum required: 10 pixels. Consider increasing pixel size or selecting a larger parcel.")
    
    # Check 3: Min distance constraint feasibility
    min_distance_meters = hard_constraints.get('min_distance', 0)
    if min_distance_meters > 0:
        min_distance_pixels = min_distance_meters / pixel_size
        # Rough heuristic: if min_distance is more than 1/4 of the parcel's smallest dimension, it's likely too large
        rows_occupied = np.any(buildable_mask, axis=1).sum()
        cols_occupied = np.any(buildable_mask, axis=0).sum()
        min_dimension = min(rows_occupied, cols_occupied)
        if min_distance_pixels > min_dimension / 4:
            raise ValueError(f"Min distance constraint ({min_distance_meters}m = {min_distance_pixels:.1f} pixels) is too large for parcel size (smallest dimension: {min_dimension} pixels). Reduce min_distance or select a larger parcel.")
    
    # Merge user-defined QD hyperparameters with defaults
    qd_config = QD_CONFIG.copy()
    if qd_hyperparams:
        qd_config.update(qd_hyperparams)
    
    # Create encoding config with user's max_height converted to floors
    encoding_config = ENCODING_CONFIG.copy()
    max_height_meters = hard_constraints.get('max_height', ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])
    max_height_floors = int(max_height_meters / ENCODING_CONFIG['meters_per_floor'])
    encoding_config['max_building_floors'] = max_height_floors
    
    encoding_obj = ParametricEncoding(encoding_config)
    
    # Store encoding config in env_config so it can be retrieved later when saving results
    env_config['encoding_config'] = encoding_config
    
    # Generate adaptive initial genome based on parcel size
    x0_adaptive = encoding_obj.get_adaptive_initial_genome(buildable_mask)
    
    # Configure surrogate model if using ML methods
    if use_surrogate:
        from backend.surrogate_evaluator import create_surrogate_wrapper
        
        # Extract parcel size from env_config (xy_length is set by create_environment)
        parcel_size_bins = ENCODING_CONFIG.get('xy_length')
        if not parcel_size_bins:
            raise ValueError("Cannot create surrogate: parcel size (xy_length) not found in ENCODING_CONFIG")
        
        # Guard: U-Net only available for parcels <= max available model size
        max_unet_size_m = max(SURROGATE_CONFIG['available_parcel_sizes_unet_m'])
        parcel_size_m = parcel_size_bins * pixel_size
        if parcel_size_m > max_unet_size_m:
            raise ValueError(
                f"U-Net model not available for {parcel_size_m:.0f}m parcel "
                f"(max supported: {max_unet_size_m}m). "
                f"Please select a geometric method (Street Canyon or Simple Porosity)."
            )
        
        surrogate_wrapper = create_surrogate_wrapper(
            model_type=model_type,
            parcel_size_bins=parcel_size_bins,
            ucb_lambda=ucb_lambda
        )
        
        if surrogate_wrapper is None:
            raise ValueError(
                f"Could not initialize '{model_type}' model for parcel size {parcel_size_bins} bins ({parcel_size_m:.0f}m). "
                f"Check the logs for details (possible CUDA/GPU issue). "
                f"You can also try a geometric method (Street Canyon or Simple Porosity)."
            )
        
        env_config['use_surrogate'] = True
        env_config['surrogate_wrapper'] = surrogate_wrapper
        print(f"Using surrogate model: {model_type} (parcel_size={parcel_size_bins} bins, {parcel_size_m:.0f}m)")
    else:
        env_config['use_surrogate'] = False
        env_config['surrogate_wrapper'] = None
        print(f"Using geometric evaluation: {model_type}")
    
    sample_genome = np.random.randn(encoding_obj.get_dimension())
    # create_debug_plots(env_config, sample_genome, encoding_obj)
    progress_callback(10, "Starting optimization...")
    archive = run_qd_optimization(
        encoding_obj, env_config, qd_config, x0_adaptive, progress_callback)
    progress_callback(100, "Optimization complete.")
    
    # Final check: If archive is still empty, provide detailed error
    if archive.stats.num_elites == 0:
        raise RuntimeError(
            "Optimization completed but archive is empty. No valid solutions were found. "
            "This typically indicates that the constraints are too restrictive for the selected parcel. "
            "Try:\n"
            "  1. Reducing the min_distance constraint\n"
            "  2. Increasing the max_height constraint\n"
            "  3. Selecting a larger or more regular-shaped parcel\n"
            "  4. Running the diagnostic page to identify specific issues"
        )
    
    return archive, env_config['labels'], env_config
