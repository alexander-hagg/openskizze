# backend/evaluation.py

import numpy as np
from scipy.ndimage import label, center_of_mass, rotate
import multiprocessing
from backend.config import DOMAIN_CONFIG # Import DOMAIN_CONFIG for pixel size

def compute_fitness(heightmap_3d: np.ndarray, wind_direction: int) -> float:
    # --- DEBUG LOG for Requirement 7 ---
    # print(f"  [DEBUG-FITNESS] Calculating porosity with wind direction: {wind_direction}°")
    
    # Rotation angle is based on meteorological degrees (0°=North, 90°=East)
    rotated_env = rotate(heightmap_3d, angle=wind_direction, axes=(0, 1), reshape=False, order=0)
    
    projection = np.sum(rotated_env, axis=1)
    open_columns = np.sum(projection == 0)
    total_columns = projection.shape[0] * projection.shape[1]
    
    porosity = open_columns / total_columns if total_columns > 0 else 0.0
    
    # --- Check for Requirement 8 ---
    # Clamp value for safety, although it should mathematically be in [0, 1]
    return np.clip(porosity, 0.0, 1.0)

def calculate_features(heightmap: np.ndarray, buildable_area_in_sq_meters: float) -> list:
    grid_size = heightmap.size
    occupied = heightmap > 0
    building_coverage = np.sum(occupied) / grid_size if grid_size > 0 else 0.0
    building_heights = heightmap[occupied]
    if not building_heights.any(): return [0.0] * 8
    avg_height = np.mean(building_heights)
    height_variability = np.std(building_heights)
    
    occupancy_grid_2d = heightmap > 0
    _, num_buildings = label(occupancy_grid_2d)
    
    if num_buildings > 1:
        centroids = np.array(center_of_mass(occupancy_grid_2d, label(occupancy_grid_2d)[0], range(1, num_buildings + 1)))
        diff = centroids[:, None, :] - centroids[None, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        avg_spacing = np.mean(dists[np.triu_indices(num_buildings, k=1)])
    else: avg_spacing = 0.0
    
    # --- FIX for Requirement 5 & 6: Correct FSR Calculation ---
    pixel_area = DOMAIN_CONFIG['pixel_size_in_meters'] ** 2
    total_floor_area_in_sq_meters = np.sum(heightmap) * pixel_area
    floor_space_ratio = total_floor_area_in_sq_meters / buildable_area_in_sq_meters if buildable_area_in_sq_meters > 0 else 0.0
    
    center_y, center_x = center_of_mass(heightmap)

    return [
        building_coverage, avg_height, height_variability, num_buildings,
        avg_spacing, floor_space_ratio, center_x, center_y
    ]

def eval_solution(genome: np.ndarray, encoding_obj, env_config: dict) -> np.ndarray:
    heightmap_2d_solution = encoding_obj.express(env_config['buildable_mask'], genome)
    
    design_3d = np.zeros_like(env_config['env_3d_fixed'])
    for r in range(heightmap_2d_solution.shape[0]):
        for c in range(heightmap_2d_solution.shape[1]):
            h = int(heightmap_2d_solution[r, c])
            if h > 0: design_3d[r, c, :h] = 1
            
    combined_env_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
    fitness = compute_fitness(combined_env_3d, env_config['wind_direction'])
    
    # Pass the dynamic buildable area to the feature calculator
    features = calculate_features(heightmap_2d_solution, env_config['buildable_area_in_sq_meters'])
    
    return np.concatenate(([fitness], features, heightmap_2d_solution.flatten()))

def eval_batch(genomes: list, encoding_obj, env_config: dict, pool) -> np.ndarray:
    results = pool.starmap(eval_solution, [(g, encoding_obj, env_config) for g in genomes])
    return np.array(results)