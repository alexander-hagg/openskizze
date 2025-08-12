#
# backend/evaluation.py (Final Corrected Version)
#
import numpy as np
from scipy.ndimage import label, center_of_mass, rotate
import multiprocessing
from backend.config import DOMAIN_CONFIG, ENCODING_CONFIG

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
        # --- FIX for Magic Number ---
        # Return a zero vector with the length of the total number of possible features.
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
    design_3d = np.zeros_like(env_config['env_3d_fixed'])
    for r in range(heightmap_2d_solution.shape[0]):
        for c in range(heightmap_2d_solution.shape[1]):
            h = int(heightmap_2d_solution[r, c])
            if h > 0: design_3d[r, c, :h] = 1
            
    combined_env_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
    fitness = compute_fitness(combined_env_3d, env_config['wind_direction'])
    
    # --- DYNAMIC FEATURE SELECTION ---
    # 1. Calculate all 8 possible features.
    all_features = calculate_all_features(
        heightmap_2d_solution,
        env_config['buildable_mask'],
        env_config['buildable_area_in_sq_meters']
    )
    # 2. Filter the features based on the indices provided in the env_config.
    selected_features = all_features[env_config['selected_features']]
    
    return np.concatenate(([fitness], selected_features, heightmap_2d_solution.flatten()))

def eval_batch(genomes: list, encoding_obj, env_config: dict, pool) -> np.ndarray:
    results = pool.starmap(eval_solution, [(g, encoding_obj, env_config) for g in genomes])
    return np.array(results)