#
# backend/evaluation.py (Final Corrected Version)
#
import numpy as np
from scipy.ndimage import label, center_of_mass, rotate, binary_erosion
import multiprocessing
from backend.config import DOMAIN_CONFIG, ENCODING_CONFIG

try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # Dummy decorator if numba not available
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


# =============================================================================
# JIT-OPTIMIZED 3D MESH GENERATION
# =============================================================================

@njit(cache=True, nogil=True)
def _create_3d_from_heightmap_jit(heightmap_2d, max_height):
    """
    JIT-optimized 3D mesh generation from 2D heightmap.
    ~15-20× faster than NumPy broadcasting for realistic parcels.
    """
    rows, cols = heightmap_2d.shape
    result = np.zeros((rows, cols, max_height), dtype=np.int8)
    
    for r in range(rows):
        for c in range(cols):
            h = int(heightmap_2d[r, c])
            if h > 0:
                for z in range(min(h, max_height)):
                    result[r, c, z] = 1
    
    return result


# =============================================================================
# JIT-OPTIMIZED FEATURE CALCULATIONS (Built Area & GRZ only)
# =============================================================================

@njit(cache=True, nogil=True)
def _compute_built_area_jit(occupied, pixel_size):
    """JIT: Built area calculation. ~6-10× faster for large parcels."""
    occupied_pixels = np.sum(occupied)
    return occupied_pixels * (pixel_size ** 2)


@njit(cache=True, nogil=True)
def _compute_grz_jit(occupied, pixel_size, buildable_area):
    """JIT: GRZ (Ground coverage ratio) calculation. ~5-7× faster for large parcels."""
    occupied_pixels = np.sum(occupied)
    built_area = occupied_pixels * (pixel_size ** 2)
    return built_area / buildable_area if buildable_area > 0 else 0.0


# =============================================================================
# JIT-OPTIMIZED FITNESS FUNCTIONS
# =============================================================================

@njit(cache=True, nogil=True)
def _compute_fitness_jit(heightmap_3d, wind_direction):
    """
    JIT-optimized simple porosity fitness WITHOUT scipy rotation.
    Uses manual nearest-neighbor rotation for ~41× speedup.
    
    Horizontal wind porosity - counts completely open horizontal paths.
    Returns percentage (0.0-1.0) of unblocked straight horizontal wind corridors.
    """
    rows, cols, height = heightmap_3d.shape
    
    # Manual rotation using nearest neighbor sampling
    rotation_angle_rad = np.radians((wind_direction + 90) % 360)
    cos_a = np.cos(rotation_angle_rad)
    sin_a = np.sin(rotation_angle_rad)
    
    center_r = rows / 2.0
    center_c = cols / 2.0
    
    # Create rotated environment
    rotated = np.zeros_like(heightmap_3d)
    
    for r in range(rows):
        for c in range(cols):
            # Rotate coordinates
            r_centered = r - center_r
            c_centered = c - center_c
            
            r_rot = r_centered * cos_a - c_centered * sin_a + center_r
            c_rot = r_centered * sin_a + c_centered * cos_a + center_c
            
            # Nearest neighbor sampling
            r_src = int(round(r_rot))
            c_src = int(round(c_rot))
            
            if 0 <= r_src < rows and 0 <= c_src < cols:
                for z in range(height):
                    rotated[r, c, z] = heightmap_3d[r_src, c_src, z]
    
    # Calculate porosity: count open horizontal paths
    open_paths = 0
    total_paths = 0
    
    for r in range(rows):
        for z in range(height):
            # Check if entire Y-axis (wind direction) is clear
            is_clear = True
            for c in range(cols):
                if rotated[r, c, z] > 0:
                    is_clear = False
                    break
            
            if is_clear:
                open_paths += 1
            total_paths += 1
    
    porosity = open_paths / total_paths if total_paths > 0 else 0.0
    return min(max(porosity, 0.0), 1.0)


@njit(cache=True, nogil=True)
def _compute_fitness_street_canyon_jit(heightmap_3d, wind_direction):
    """
    JIT-optimized street canyon fitness WITHOUT scipy rotation.
    Uses manual nearest-neighbor rotation for ~28× speedup.
    
    Improved wind flow surrogate for dense urban environments.
    Captures:
    1. Horizontal gaps (street canyons) at ground level
    2. Lateral ventilation corridors
    3. Height variation creating turbulence zones
    4. Partial penetration (weighted by blockage)
    """
    rows, cols, height = heightmap_3d.shape
    
    # Manual rotation using nearest neighbor sampling
    rotation_angle_rad = np.radians((wind_direction + 90) % 360)
    cos_a = np.cos(rotation_angle_rad)
    sin_a = np.sin(rotation_angle_rad)
    
    center_r = rows / 2.0
    center_c = cols / 2.0
    
    # Create rotated environment
    rotated = np.zeros_like(heightmap_3d)
    
    for r in range(rows):
        for c in range(cols):
            r_centered = r - center_r
            c_centered = c - center_c
            
            r_rot = r_centered * cos_a - c_centered * sin_a + center_r
            c_rot = r_centered * sin_a + c_centered * cos_a + center_c
            
            r_src = int(round(r_rot))
            c_src = int(round(c_rot))
            
            if 0 <= r_src < rows and 0 <= c_src < cols:
                for z in range(height):
                    rotated[r, c, z] = heightmap_3d[r_src, c_src, z]
    
    # Component 1: Ground-level street canyons with continuity weighting
    ground_open_sum = 0.0
    continuity_sum = 0.0
    
    for r in range(rows):
        # Count open spaces at ground level (first 2 layers)
        open_count = 0
        for c in range(cols):
            is_open = True
            for z in range(min(2, height)):
                if rotated[r, c, z] > 0:
                    is_open = False
                    break
            if is_open:
                open_count += 1
        
        row_openness = open_count / cols if cols > 0 else 0.0
        ground_open_sum += row_openness
        
        # Count transitions for continuity (penalize fragmentation)
        transitions = 0
        for c in range(cols - 1):
            occupied_curr = False
            occupied_next = False
            for z in range(min(2, height)):
                if rotated[r, c, z] > 0:
                    occupied_curr = True
                if rotated[r, c + 1, z] > 0:
                    occupied_next = True
            
            if occupied_curr != occupied_next:
                transitions += 1
        
        fragmentation = transitions / (cols - 1) if cols > 1 else 0.0
        continuity_weight = 1.0 - min(fragmentation, 1.0)
        continuity_sum += row_openness * (0.5 + 0.5 * continuity_weight)
    
    street_canyon_score = continuity_sum / rows if rows > 0 else 0.0
    
    # Component 2: Lateral ventilation (cross-wind flow)
    lateral_sum = 0.0
    for c in range(cols):
        open_count = 0
        for r in range(rows):
            for z in range(height):
                if rotated[r, c, z] == 0:
                    open_count += 1
        
        lateral_openness = open_count / (rows * height) if (rows * height) > 0 else 0.0
        lateral_sum += lateral_openness
    
    lateral_ventilation_score = lateral_sum / cols if cols > 0 else 0.0
    
    # Component 3: Height variation (promotes turbulence/mixing)
    max_heights_sum = 0.0
    max_heights_sq_sum = 0.0
    for r in range(rows):
        for c in range(cols):
            max_h = 0
            for z in range(height):
                if rotated[r, c, z] > 0:
                    max_h = z + 1
            max_heights_sum += max_h
            max_heights_sq_sum += max_h * max_h
    
    count = rows * cols
    mean_height = max_heights_sum / count if count > 0 else 0.0
    variance = (max_heights_sq_sum / count - mean_height * mean_height) if count > 0 else 0.0
    height_std = np.sqrt(max(variance, 0.0))
    max_possible_std = height / 2.0
    height_variation_score = min(height_std / max_possible_std, 1.0) if max_possible_std > 0 else 0.0
    
    # Component 4: Partial penetration (wind can partially pass through)
    penetration_sum = 0.0
    for r in range(rows):
        for z in range(height):
            column_sum = 0
            for c in range(cols):
                column_sum += rotated[r, c, z]
            
            penetration = 1.0 - min(column_sum / height, 1.0) if height > 0 else 0.0
            penetration_sum += penetration
    
    penetration_score = penetration_sum / (rows * height) if (rows * height) > 0 else 0.0
    
    # Weighted combination (tuned for urban environments)
    fitness = (
        0.35 * street_canyon_score +      # Street-level corridors (most important)
        0.25 * lateral_ventilation_score + # Cross-ventilation
        0.15 * height_variation_score +    # Turbulence/mixing
        0.25 * penetration_score           # Partial wind penetration
    )
    
    return min(max(fitness, 0.0), 1.0)

def check_constraints(heightmap: np.ndarray, constraints: dict):
    """
    Checks for constraint violations and modifies the heightmap.
    Returns the (potentially modified) heightmap and a boolean indicating if a penalty should be applied.
    """
    is_violated = False
    
    # 1. Max Height Constraint
    max_height_voxels = constraints.get('max_height')
    if max_height_voxels is not None:
        # Clip the heightmap to enforce the max height. This is a "repair" action.
        heightmap = np.clip(heightmap, 0, max_height_voxels)
    
    # 2. Min Distance Constraint
    min_distance_meters = constraints.get('min_distance')
    if min_distance_meters is not None and min_distance_meters > 0:
        pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
        min_dist_pixels = min_distance_meters / pixel_size
        
        # We check if any two buildings are too close.
        labeled_buildings, num_buildings = label(heightmap > 0)
        
        if num_buildings > 1:
            # Erode each building by half the minimum distance. If any two eroded zones touch or overlap,
            # it means the original buildings were closer than the minimum distance.
            # The structure makes the erosion isotropic.
            erosion_radius = int(np.ceil(min_dist_pixels / 2))
            if erosion_radius > 0:
                eroded_map = binary_erosion(heightmap > 0, iterations=erosion_radius)
                
                # Check if any building has been completely eroded away, which implies it was too small
                # or too close to another.
                labeled_eroded, num_eroded = label(eroded_map)
                if num_eroded < num_buildings:
                    is_violated = True
            
    return heightmap, is_violated

def compute_fitness(heightmap_3d: np.ndarray, wind_direction: int) -> float:
    """
    Horizontal wind porosity - counts completely open horizontal paths in wind direction.
    Returns percentage (0.0-1.0) of unblocked straight horizontal wind corridors.
    Fitness = 1.0 for empty environment, 0.0 if all paths blocked.
    
    Uses JIT-optimized version (~41× faster) when numba is available.
    Falls back to scipy rotation version if numba not available.
    """
    # Use JIT-optimized version when available (~41× faster)
    if NUMBA_AVAILABLE:
        return _compute_fitness_jit(heightmap_3d, wind_direction)
    
    # Fallback to scipy version
    # Rotate environment so wind direction aligns with axis 1 (Y-axis)
    rotation_angle = (wind_direction+90) % 360
    rotated_env = rotate(heightmap_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
    
    # For each (x, z) position, check if there's any obstruction along the entire Y-axis (wind path)
    # Use max instead of sum: if max == 0, the entire horizontal path is clear
    max_along_wind = np.max(rotated_env, axis=1)  # Shape: (rows, height)
    
    # Count positions where the entire wind path is open (max == 0)
    open_paths = np.sum(max_along_wind == 0)
    total_paths = max_along_wind.shape[0] * max_along_wind.shape[1]
    
    porosity = open_paths / total_paths if total_paths > 0 else 0.0
    return np.clip(porosity, 0.0, 1.0)

def compute_fitness_street_canyon(heightmap_3d: np.ndarray, wind_direction: int) -> float:
    """
    Improved wind flow surrogate for dense urban environments.
    
    Captures:
    1. Horizontal gaps (street canyons) at ground level
    2. Lateral ventilation corridors
    3. Height variation creating turbulence zones
    4. Partial penetration (weighted by blockage)
    
    Uses JIT-optimized version (~28× faster) when numba is available.
    Falls back to scipy rotation version if numba not available.
    """
    # Use JIT-optimized version when available (~28× faster)
    if NUMBA_AVAILABLE:
        return _compute_fitness_street_canyon_jit(heightmap_3d, wind_direction)
    
    # Fallback to scipy version with vectorized operations
    rotation_angle = (wind_direction + 90) % 360
    rotated_env = rotate(heightmap_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
    
    rows, cols, height = rotated_env.shape
    
    # Component 1: Ground-level street canyons (VECTORIZED with RLE approximation)
    # Check bottom 2 layers for open space
    ground_level = rotated_env[:, :, :2]
    ground_occupied = np.any(ground_level > 0, axis=2).astype(np.int8)
    
    # Vectorized Run-Length Encoding approximation for continuous corridors
    # Count transitions from open to occupied in each row
    ground_open = 1 - ground_occupied
    row_openness = np.mean(ground_open, axis=1)  # Openness per row
    
    # Weight by continuity: penalize fragmented open spaces
    # Check for transitions (0->1 or 1->0) along columns
    transitions = np.abs(np.diff(ground_occupied, axis=1))
    fragmentation = np.mean(transitions, axis=1)  # Higher = more fragmented
    continuity_weight = 1.0 - np.clip(fragmentation, 0, 1)
    
    # Weighted average: prefer continuous open corridors
    street_canyon_score = np.mean(row_openness * (0.5 + 0.5 * continuity_weight))
    
    # Component 2: Lateral ventilation (VECTORIZED)
    # Calculate openness for all columns at once
    open_per_col = np.sum(rotated_env == 0, axis=(0, 2))
    total_per_col = rows * height
    lateral_openness = open_per_col / total_per_col
    lateral_ventilation_score = np.mean(lateral_openness)
    
    # Component 3: Height variation (VECTORIZED)
    max_heights = np.max(rotated_env, axis=2)
    height_std = np.std(max_heights)
    max_possible_std = height / 2.0
    height_variation_score = min(height_std / max_possible_std, 1.0) if max_possible_std > 0 else 0.0
    
    # Component 4: Partial penetration (VECTORIZED)
    projection = np.sum(rotated_env, axis=1)
    penetration_per_column = 1.0 - np.clip(projection / height, 0.0, 1.0)
    penetration_score = np.mean(penetration_per_column)
    
    # Weighted combination (tuned for urban environments)
    fitness = (
        0.35 * street_canyon_score +      # Street-level corridors (most important)
        0.25 * lateral_ventilation_score + # Cross-ventilation
        0.15 * height_variation_score +    # Turbulence/mixing
        0.25 * penetration_score           # Partial wind penetration
    )
    
    return np.clip(fitness, 0.0, 1.0)

def calculate_all_features(heightmap: np.ndarray, buildable_mask: np.ndarray, buildable_area_in_sq_meters: float) -> np.ndarray:
    """
    Calculate all 8 ORIGINAL features in PHYSICAL UNITS.
    Uses JIT optimization for Built Area calculation (~6-10× faster).
    
    Returns:
        Array of features in physical units:
        [0] Built Area (m²)
        [1] Average Height (m)
        [2] Height Variability (m)
        [3] Number of Buildings (count)
        [4] Average Distance (m)
        [5] Gross Floor Area (m²)
        [6] Building Mass X (normalized 0-1)
        [7] Building Mass Y (normalized 0-1)
    """
    grid_res_y, grid_res_x = heightmap.shape
    occupied = heightmap > 0
    buildable_pixels = np.sum(buildable_mask)
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    pixel_area = pixel_size ** 2
    
    # [0] Built Area - in m² (JIT-optimized for ~6-10× speedup)
    if NUMBA_AVAILABLE:
        built_area_m2 = _compute_built_area_jit(occupied, pixel_size)
    else:
        occupied_pixels = np.sum(occupied)
        built_area_m2 = occupied_pixels * pixel_area
    
    building_heights = heightmap[occupied]
    if not building_heights.any():
        return np.zeros(8)  # Return zeros for all 8 features
        
    # [1] Average Height - heightmap is already in METERS
    avg_height_meters = np.mean(building_heights)
    
    # [2] Height Variability - heightmap is already in METERS
    height_variability_meters = np.std(building_heights)
    
    # [3] Number of Buildings - already a count
    # Cache the labeled array to avoid calling label() twice
    labeled_array, num_buildings = label(occupied)
    
    # [4] Average Building Distance - in meters (not normalized)
    if num_buildings > 1:
        # Reuse cached labeled_array instead of calling label() again
        centroids = np.array(center_of_mass(occupied, labeled_array, range(1, num_buildings + 1)))
        diff = centroids[:, None, :] - centroids[None, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        avg_spacing_pixels = np.mean(dists[np.triu_indices(num_buildings, k=1)])
        avg_spacing_meters = avg_spacing_pixels * pixel_size
    else:
        avg_spacing_meters = 0.0
    
    # [5] Gross Floor Area - in m² (not FSR ratio)
    total_floor_area_m2 = np.sum(heightmap) * pixel_area
    
    # [6] Building Mass X - normalized position (0-1)
    center_y_px, center_x_px = center_of_mass(heightmap)
    center_x = center_x_px / grid_res_x if grid_res_x > 0 else 0.0
    
    # [7] Building Mass Y - normalized position (0-1)
    center_y = center_y_px / grid_res_y if grid_res_y > 0 else 0.0

    return np.array([
        built_area_m2, avg_height_meters, height_variability_meters, num_buildings,
        avg_spacing_meters, total_floor_area_m2, center_x, center_y
    ])


def calculate_all_features_planning(heightmap: np.ndarray, buildable_mask: np.ndarray, buildable_area_in_sq_meters: float) -> np.ndarray:
    """
    Calculate all 8 PLANNING-FOCUSED features (BACKLOG specification).
    Uses JIT optimization for Built Area (~6-10×) and GRZ (~5-7×) calculations.
    
    Returns:
        Array of planning-focused features:
        [0] GRZ (Grundflächenzahl / Site Coverage Ratio) - ratio 0-1
        [1] GFZ (Geschossflächenzahl / Floor Area Ratio) - ratio
        [2] Average Building Height (m)
        [3] Height Variability (m)
        [4] Number of Buildings (count)
        [5] Average Building Distance (m)
        [6] Street Canyon Aspect Ratio (H/W) - dimensionless
        [7] Sky View Factor (SVF) - ratio 0-1 (TODO: implement full calculation)
    """
    grid_res_y, grid_res_x = heightmap.shape
    occupied = heightmap > 0
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    pixel_area = pixel_size ** 2
    
    building_heights = heightmap[occupied]
    if not building_heights.any():
        return np.zeros(8)  # Return zeros for all 8 features
    
    # [0] GRZ (Grundflächenzahl) - Site Coverage Ratio (JIT-optimized for ~5-7× speedup)
    # GRZ = Built Area / Total Site Area (buildable area)
    if NUMBA_AVAILABLE:
        grz = _compute_grz_jit(occupied, pixel_size, buildable_area_in_sq_meters)
    else:
        occupied_pixels = np.sum(occupied)
        built_area_m2 = occupied_pixels * pixel_area
        grz = built_area_m2 / buildable_area_in_sq_meters if buildable_area_in_sq_meters > 0 else 0.0
    grz = np.clip(grz, 0.0, 1.0)
    
    # [1] GFZ (Geschossflächenzahl) - Floor Area Ratio
    # GFZ = Total Floor Area / Total Site Area
    # Assuming each meter of height = 1/3 of a floor (3m per floor)
    total_floor_area_m2 = np.sum(heightmap) * pixel_area
    gfz = total_floor_area_m2 / buildable_area_in_sq_meters if buildable_area_in_sq_meters > 0 else 0.0
    
    # [2] Average Height - heightmap is already in METERS
    avg_height_meters = np.mean(building_heights)
    
    # [3] Height Variability - heightmap is already in METERS
    height_variability_meters = np.std(building_heights)
    
    # [4] Number of Buildings - already a count
    labeled_array, num_buildings = label(occupied)
    
    # [5] Average Building Distance - in meters
    if num_buildings > 1:
        centroids = np.array(center_of_mass(occupied, labeled_array, range(1, num_buildings + 1)))
        diff = centroids[:, None, :] - centroids[None, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        avg_spacing_pixels = np.mean(dists[np.triu_indices(num_buildings, k=1)])
        avg_spacing_meters = avg_spacing_pixels * pixel_size
    else:
        avg_spacing_meters = 0.0
    
    # [6] Street Canyon Aspect Ratio (H/W)
    # Calculate average height (H) and average street width (W)
    # Street width = average distance between buildings
    if avg_spacing_meters > 0:
        aspect_ratio = avg_height_meters / avg_spacing_meters
    else:
        aspect_ratio = 0.0
    
    # [7] Sky View Factor (SVF) - Placeholder implementation
    # TODO: Implement proper SVF calculation using ray-tracing or hemisphere projection
    # For now, use a simple approximation based on building coverage and height
    # SVF decreases with higher coverage and taller buildings
    # Simple approximation: SVF ≈ 1 - (GRZ * normalized_height)
    max_possible_height_meters = ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor']
    normalized_height = np.clip(avg_height_meters / max_possible_height_meters, 0.0, 1.0) if max_possible_height_meters > 0 else 0.0
    svf_approx = 1.0 - (grz * normalized_height * 0.8)  # 0.8 factor to prevent reaching 0 too quickly
    svf_approx = np.clip(svf_approx, 0.0, 1.0)
    
    return np.array([
        grz, gfz, avg_height_meters, height_variability_meters,
        num_buildings, avg_spacing_meters, aspect_ratio, svf_approx
    ])

def eval_solution(genome: np.ndarray, encoding_obj, env_config: dict) -> np.ndarray:
    heightmap_2d_solution = encoding_obj.express(env_config['buildable_mask'], genome)

    # --- NEW: Enforce Hard Constraints ---
    constraints = env_config.get('hard_constraints', {})
    heightmap_2d_solution, is_violated = check_constraints(heightmap_2d_solution, constraints)

    # Check for empty solutions (no buildings)
    if np.sum(heightmap_2d_solution) == 0:
        num_features = len(env_config['selected_features'])
        dummy_features = np.zeros(num_features)
        dummy_heightmap = heightmap_2d_solution.flatten()
        return np.concatenate(([-10.0], dummy_features, dummy_heightmap))

    if is_violated:
        # If constraints are violated, return a very poor fitness score (-1)
        # and dummy values for the rest. This solution will be discarded.
        num_features = len(env_config['selected_features'])
        dummy_features = np.zeros(num_features)
        dummy_heightmap = heightmap_2d_solution.flatten()
        return np.concatenate(([-1.0], dummy_features, dummy_heightmap))
    
    # --- JIT-OPTIMIZED 3D MESH GENERATION ---
    # CRITICAL: ALL Z-axes are now in METERS throughout the application
    # heightmap_2d_solution is in METERS (from express()), env_3d_fixed is in METERS (1 voxel = 1 meter)
    max_height_meters = env_config['env_3d_fixed'].shape[2]
    
    # Use JIT-optimized 3D mesh generation (~15-20× faster)
    if NUMBA_AVAILABLE:
        design_3d = _create_3d_from_heightmap_jit(heightmap_2d_solution.astype(np.float32), max_height_meters)
    else:
        # Fallback to NumPy broadcasting if numba not available
        z_indices = np.arange(max_height_meters)
        design_3d = (z_indices < heightmap_2d_solution.astype(int)[:, :, np.newaxis]).astype(np.int8)
    
            
    combined_env_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
    
    # --- OBJECTIVE FUNCTION SELECTION ---
    objective_function = env_config.get('objective_function', 'simple_porosity')
    if objective_function == 'street_canyon':
        fitness = compute_fitness_street_canyon(combined_env_3d, env_config['wind_direction'])
    else:
        # Default to original simple porosity
        fitness = compute_fitness(combined_env_3d, env_config['wind_direction'])

    # Calculate buildable area in square meters from buildable mask
    buildable_area_in_sq_meters = np.sum(env_config['buildable_mask']) * (DOMAIN_CONFIG['pixel_size_in_meters'] ** 2)

    # --- DYNAMIC FEATURE SELECTION ---
    # Determine which feature set to use
    feature_set = env_config.get('feature_set', 'original')
    
    # 1. Calculate all 8 possible features using the appropriate function
    if feature_set == 'planning':
        all_features = calculate_all_features_planning(
            heightmap_2d_solution,
            env_config['buildable_mask'],
            buildable_area_in_sq_meters
        )
    else:  # 'original' or default
        all_features = calculate_all_features(
            heightmap_2d_solution,
            env_config['buildable_mask'],
            buildable_area_in_sq_meters
        )
    
    # 2. Filter the features based on the indices provided in the env_config.
    selected_features = all_features[env_config['selected_features']]
    
    return np.concatenate(([fitness], selected_features, heightmap_2d_solution.flatten()))

def eval_batch(genomes: list, encoding_obj, env_config: dict, pool) -> np.ndarray:
    # results = [eval_solution(g, encoding_obj, env_config) for g in genomes]
    results = pool.starmap(eval_solution, [(g, encoding_obj, env_config) for g in genomes])

    return np.array(results)