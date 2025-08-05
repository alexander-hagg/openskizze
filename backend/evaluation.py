# backend/evaluation.py

import numpy as np
from scipy.ndimage import label, center_of_mass, rotate
import multiprocessing
from backend.config import ENCODING_CONFIG

def compute_fitness(heightmap_3d: np.ndarray, wind_direction: int) -> float:
    """
    Calculates fitness based on directional porosity.
    Rotates the 3D environment so wind is always coming from the 'left' (axis 1),
    then calculates the fraction of open vertical columns.
    """
    # Rotate the environment so the wind direction is aligned with the positive y-axis (from left to right)
    # Rotation angle is based on meteorological degrees (0°=North, 90°=East)
    # We rotate around the Z-axis (axes=(0, 1))
    rotated_env = rotate(heightmap_3d, angle=wind_direction, axes=(0, 1), reshape=False, order=0)

    # Project the 3D environment onto a 2D plane by summing building voxels along the wind's path (axis 1)
    projection = np.sum(rotated_env, axis=1)
    
    # An open column is one with no buildings in it (sum of heights is 0)
    open_columns = np.sum(projection == 0)
    
    # Total number of columns is the product of the other two dimensions
    total_columns = projection.shape[0] * projection.shape[1]
    
    porosity = open_columns / total_columns if total_columns > 0 else 0.0
    return porosity

def calculate_features(heightmap: np.ndarray) -> list:
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
    total_floor_space = np.sum(heightmap)
    floor_space_ratio = total_floor_space / (grid_size * ENCODING_CONFIG['z_length'])
    center_y, center_x = center_of_mass(heightmap)
    return [building_coverage, avg_height, height_variability, num_buildings, avg_spacing, floor_space_ratio, center_x, center_y]

def eval_solution(genome: np.ndarray, encoding_obj, env_config: dict) -> np.ndarray:
    heightmap_2d_solution = encoding_obj.express(env_config['buildable_mask'], genome)
    
    design_3d = np.zeros_like(env_config['env_3d_fixed'])
    for r in range(heightmap_2d_solution.shape[0]):
        for c in range(heightmap_2d_solution.shape[1]):
            h = int(heightmap_2d_solution[r, c])
            if h > 0: design_3d[r, c, :h] = 1
            
    combined_env_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
    
    # Pass the wind direction from the environment config to the fitness function
    fitness = compute_fitness(combined_env_3d, env_config['wind_direction'])

    features = calculate_features(heightmap_2d_solution)
    
    return np.concatenate(([fitness], features, heightmap_2d_solution.flatten()))

def eval_batch(genomes: list, encoding_obj, env_config: dict, pool) -> np.ndarray:
    results = pool.starmap(eval_solution, [(g, encoding_obj, env_config) for g in genomes])
    return np.array(results)