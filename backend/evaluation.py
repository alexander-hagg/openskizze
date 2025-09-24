#
# backend/evaluation.py (Final Corrected Version)
#
import numpy as np
from scipy.ndimage import label, center_of_mass, rotate, binary_erosion
import multiprocessing
from backend.config import DOMAIN_CONFIG, ENCODING_CONFIG

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
    rotation_angle = (wind_direction + 90) % 360
    rotated_env = rotate(heightmap_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
    projection = np.sum(rotated_env, axis=1)
    open_columns = np.sum(projection == 0)
    total_columns = projection.shape[0] * projection.shape[1]
    porosity = open_columns / total_columns if total_columns > 0 else 0.0
    return np.clip(porosity, 0.0, 1.0)

def calculate_all_features(heightmap: np.ndarray, buildable_mask: np.ndarray, buildable_area_in_sq_meters: float) -> np.ndarray:
    grid_res_y, grid_res_x = heightmap.shape
    occupied = heightmap > 0
    buildable_pixels = np.sum(buildable_mask)
    
    building_coverage = np.sum(occupied) / buildable_pixels if buildable_pixels > 0 else 0.0
    
    building_heights = heightmap[occupied]
    if not building_heights.any():
        return np.zeros(len(DOMAIN_CONFIG['labels']))
        
    avg_height = np.mean(building_heights)
    height_variability = np.std(building_heights)
    _, num_buildings = label(occupied)
    
    if num_buildings > 1:
        centroids = np.array(center_of_mass(occupied, label(occupied)[0], range(1, num_buildings + 1)))
        diff = centroids[:, None, :] - centroids[None, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        avg_spacing_pixels = np.mean(dists[np.triu_indices(num_buildings, k=1)])
        max_dist = np.sqrt(grid_res_x**2 + grid_res_y**2)
        avg_spacing = avg_spacing_pixels / max_dist if max_dist > 0 else 0.0
    else: avg_spacing = 0.0
    
    pixel_area = DOMAIN_CONFIG['pixel_size_in_meters'] ** 2
    total_floor_area_sq_meters = np.sum(heightmap) * pixel_area
    floor_space_ratio = total_floor_area_sq_meters / buildable_area_in_sq_meters if buildable_area_in_sq_meters > 0 else 0.0
    
    center_y_px, center_x_px = center_of_mass(heightmap)
    center_x = center_x_px / grid_res_x if grid_res_x > 0 else 0.0
    center_y = center_y_px / grid_res_y if grid_res_y > 0 else 0.0

    return np.array([
        building_coverage, avg_height, height_variability, num_buildings,
        avg_spacing, floor_space_ratio, center_x, center_y
    ])

def eval_solution(genome: np.ndarray, encoding_obj, env_config: dict) -> np.ndarray:
    heightmap_2d_solution = encoding_obj.express(env_config['buildable_mask'], genome)

    # --- NEW: Enforce Hard Constraints ---
    constraints = env_config.get('hard_constraints', {})
    heightmap_2d_solution, is_violated = check_constraints(heightmap_2d_solution, constraints)

    if is_violated:
        # If constraints are violated, return a very poor fitness score (-1)
        # and dummy values for the rest. This solution will be discarded.
        num_features = len(env_config['selected_features'])
        dummy_features = np.zeros(num_features)
        dummy_heightmap = heightmap_2d_solution.flatten()
        return np.concatenate(([-1.0], dummy_features, dummy_heightmap))
    
    # --- OPTIMIZED 3D MESH GENERATION ---
    # Create an array of z-axis indices: [0, 1, 2, ..., max_height-1]
    max_height = env_config['env_3d_fixed'].shape[2]
    z_indices = np.arange(max_height)

    # Use NumPy broadcasting to compare the height at each (r, c) with the z_indices.
    design_3d = (z_indices < heightmap_2d_solution.astype(int)[:, :, np.newaxis]).astype(np.int8)
    
            
    combined_env_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
    fitness = compute_fitness(combined_env_3d, env_config['wind_direction'])

    # Calculate buildable area in square meters from buildable mask
    buildable_area_in_sq_meters = np.sum(env_config['buildable_mask']) * (DOMAIN_CONFIG['pixel_size_in_meters'] ** 2)

    # --- DYNAMIC FEATURE SELECTION ---
    # 1. Calculate all 8 possible features.
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