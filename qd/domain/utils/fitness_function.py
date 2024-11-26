"""Fitness function."""
from typing import Dict, List, Tuple
import copy
import sys

import numpy as np
from scipy.ndimage import label
from scipy.stats import norm, uniform

from functools import reduce
import operator


sys.path.insert(0, "qd/util")
import maptorange

import matplotlib.pyplot as plt
from PIL import Image

def norm2unif(x, min=0, max=1, mu=None, sd=None):
    if mu is None:
        mu = np.mean(x)
    if sd is None:
        sd = np.std(x, ddof=1)  # Using ddof=1 for sample standard deviation, matching R's default
    
    # Convert x from a normal distribution to probabilities
    p = norm.cdf(x, mu, sd)
    
    # Convert probabilities to a uniform distribution
    return uniform.ppf(p, min, max)

def ribs_to_genome(genome, genome_template, mu = 0.0, sigma = 1.0):
    _, num_act, num_weights = genome_template.get_dimension()
    num_available_act = len(genome_template.genes.act_funcs)
    # Genome is divided into two parts: weights and activation functions. 
    weights = genome[num_act:]
    # For the activation functions
    activation_indices = genome[:num_act]
    activation_indices = norm2unif(activation_indices, mu = mu, sd = sigma)
    activation_indices = num_available_act * activation_indices
    activation_indices = np.floor(activation_indices).astype(int)
    activation_indices = np.clip(activation_indices, 0, num_available_act-1)
    genome_template.set_genome(activation_indices.tolist(), weights.tolist())
    return copy.deepcopy(genome_template)

def ribs_eval_cppn(solution, genome_template, genome_config, mu = 0.0, sigma = 1.0):
    """
    Turn pyribs solution into openskizze Genomes and evaluate. 
    Assumption: pyribs mutation operators always operate using a Gaussian distribution

    Returns:
        value, npt.NDArray that hold fitness and feature values
    """
    population = []
    genome = ribs_to_genome(solution, genome_template, mu, sigma)
    population.append(genome)
    fitness, features, _, heightmap, _ = get(population, genome_config)
    results = np.vstack([fitness[0], features.transpose(), heightmap[0].reshape(heightmap[0].size,-1)])
    return results

def get(list_genomes: List, domain: Dict) -> Tuple:
    """
    Compute the fitness, the features, the phenotypes, and the raw features of the genomes.

    Args:
        list_genomes (List): List of objects that represent individuals.

        domain (Dict): The parameters of the experiment.

    Returns:
        Tuple(fitness, features, phenotypes, raw_features)
    """
    # Express shapes
    fitness = np.zeros(shape=[len(list_genomes), 1])
    # Populate raw_features with all features, we will subselect afterwards
    raw_features = np.zeros(shape=[len(list_genomes), len(domain.get("alg").get("labels"))])
    phenotypes = []
    phenotypes_heightmaps = []

    for i in range(len(list_genomes)):
        phenotypes.append(list_genomes[i].express(as_height_map=False))
        phenotypes_heightmaps.append(list_genomes[i].express(as_height_map=True))
        meter_squared_per_cell = (
            domain.get("alg").get("substrate_length")
            / domain.get("solution").get("num_grid_cells")
        ) ** 2.0 * (3.0 ** 2)
        
        occupancy_grid = phenotypes[i][:, :, 0]

        living_space_area = np.sum(phenotypes[i]) * meter_squared_per_cell
        footprint = np.sum(occupancy_grid) * meter_squared_per_cell

        windblock_area_NS = np.sum(phenotypes[i], axis=0)
        windblock_area_NS = windblock_area_NS > 0
        windblock_area_NS = np.sum(windblock_area_NS) * meter_squared_per_cell
        
        windblock_area_WE = np.sum(phenotypes[i], axis=1)
        windblock_area_WE = windblock_area_WE > 0
        windblock_area_WE = np.sum(windblock_area_WE) * meter_squared_per_cell
        
        # Count the number of buildings, either using 4- or 9-connectivity
        structure4 = np.array([[0, 1, 0],
                               [1, 1, 1],
                               [0, 1, 0]])  # 4-connectivity
        structure9 = np.array([[1, 1, 1],
                               [1, 1, 1],
                               [1, 1, 1]])  # 9-connectivity
        connection_directions = structure4
        img = (occupancy_grid>0).astype(int)
        _, num_buildings = label(img, connection_directions)

        # Step 1: Extract the occupancy grid (assuming occupancy is in the first channel)
        empty_cells = (occupancy_grid == 0).astype(int)
        n_rows, n_cols = empty_cells.shape

        # Step 2: Initialize DP table to store the number of ways to reach each cell
        dp = np.zeros_like(empty_cells, dtype=np.float64)

        # Initialize the first row (south edge)
        dp[0, :] = empty_cells[0, :]
        # Step 3: Iterate through the grid
        for row in range(1, n_rows):
            for col in range(n_cols):
                if empty_cells[row, col]:
                    # Sum the number of ways to reach adjacent cells in the previous row
                    total_paths = 0
                    for delta_col in [-1, 0, 1]:  # Adjacent positions: west, straight, east
                        prev_col = col + delta_col
                        if 0 <= prev_col < n_cols:
                            total_paths += dp[row - 1, prev_col]
                    dp[row, col] = total_paths
        
        # Compute the logarithm of the number of paths
        log_dp = np.log(dp + 1e-10)  # Add a small value to avoid log(0)

        # Sum the logs in the last row
        log_estimated_paths = np.logaddexp.reduce(log_dp[-1, :])

        # print(f"Logarithm of estimated number of paths for phenotype {i}: {log_estimated_paths}")

        # fitness[i] = 2.0 / (1 + (windblock_area_NS/domain.get("alg").get("feat_ranges")[1][4]))-1
        fitness[i] = log_estimated_paths
        # Penalize if number of buildings is too high
        if num_buildings > 10:
            fitness[i] = fitness[i] / (num_buildings)

        raw_features[i, :] = [
            footprint,
            living_space_area,
            num_buildings,
            windblock_area_NS,
            windblock_area_WE,
            log_estimated_paths,
        ]        
                

    # features = raw_features[
    #     :,
    #     [
    #         domain.get("algorithm_parameters").get("features")[0],
    #         domain.get("algorithm_parameters").get("features")[1],
    #         domain.get("algorithm_parameters").get("features")[2],
    #         domain.get("algorithm_parameters").get("features")[3],
    #     ],
    # ]
    features = raw_features[:,domain.get("alg").get("features")]
    # for fid in range(features.shape[1]):
    #     features[:, fid] = maptorange.do(
    #         features[:, fid],
    #         domain.get("algorithm_parameters").get("feat_ranges")[0][
    #             domain.get("algorithm_parameters").get("features")[fid]
    #         ],
    #         domain.get("algorithm_parameters").get("feat_ranges")[1][
    #             domain.get("algorithm_parameters").get("features")[fid]
    #         ],
    #     )
    fitness = np.transpose(fitness)
    
    return fitness, features, phenotypes, phenotypes_heightmaps, raw_features
