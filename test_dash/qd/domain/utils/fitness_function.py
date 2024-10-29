"""Fitness function."""
from typing import Dict, List, Tuple
import copy
import sys

import numpy as np
from scipy.ndimage import label
from scipy.stats import norm, uniform

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

def ribs_eval_cppn(solution, genome_template, genome_config, mu = 0.0, sigma = 1.0, get_full_data = False):
    """
    Turn pyribs solution into openskizze Genomes and evaluate. 
    Assumption: pyribs mutation operators always operate using a Gaussian distribution

    Returns:
        value, npt.NDArray that hold fitness and feature values
    """
    population = []
    genome = ribs_to_genome(solution, genome_template, mu, sigma)
    population.append(genome)
    if get_full_data:
        results = get(population, genome_config)
    else:
        fitness, features, _, _, _ = get(population, genome_config)
        results = np.vstack([fitness[0], features.transpose()])
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
    raw_features = np.zeros(shape=[len(list_genomes), 5])
    phenotypes = []
    phenotypes_heightmaps = []

    for i in range(len(list_genomes)):
        phenotypes.append(list_genomes[i].express(as_height_map=False))
        phenotypes_heightmaps.append(list_genomes[i].express(as_height_map=True))
        meter_squared_per_cell = (
            domain.get("algorithm_parameters").get("substrate_length")
            / domain.get("methods").get("num_grid_cells")
        ) ** 2.0 * (3.0 ** 2)
        
        living_space_area = np.sum(phenotypes[i]) * meter_squared_per_cell
        footprint = np.sum(phenotypes[i], axis=2)
        footprint = footprint > 0
        footprint = np.sum(footprint) * meter_squared_per_cell

        windblock_area = np.sum(phenotypes[i], axis=0)
        windblock_area = windblock_area > 0
        windblock_area = np.sum(windblock_area) * meter_squared_per_cell
        if windblock_area == 0:
            windblock_area = 9999

        
        windperpendicular_area = np.sum(phenotypes[i], axis=1)
        windperpendicular_area = windperpendicular_area > 0
        windperpendicular_area = np.sum(windperpendicular_area) * meter_squared_per_cell
        
        connection_directions = np.ones((3, 3), dtype=int)
        img = (phenotypes[i]>0).astype(int)
        _, num_buildings = label(np.sum(img, axis=2), connection_directions)
        
        raw_features[i, :] = [
            footprint,
            living_space_area,
            windperpendicular_area,
            num_buildings,
            windblock_area,
        ]
        
        
        #fitness[i] = (
        #    1.0 / (1 + windblock_area)  ) ** (1 / 5)
        
        # TODO get rid of magic numbers! Get those from config instead
        fitness[i] = 2.0 / (1 + (windblock_area/810))-1
        # Penalize if number of buildings is too high
        if num_buildings > 10:
            fitness[i] = 1.0 / (num_buildings**2)
        

    features = raw_features[
        :,
        [
            domain.get("algorithm_parameters").get("features")[0],
            domain.get("algorithm_parameters").get("features")[1],
            domain.get("algorithm_parameters").get("features")[2],
            domain.get("algorithm_parameters").get("features")[3],
        ],
    ]
    raw_features = features
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
