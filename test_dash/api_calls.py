import time
import numpy as np
import sys
import os
import shutil
import psutil
import multiprocessing
import yaml
import pickle

from datetime import datetime
from typing import Dict

import matplotlib.pyplot as plt

from ribs.archives import GridArchive
from ribs.emitters import EvolutionStrategyEmitter
from ribs.schedulers import Scheduler
from ribs.visualize import parallel_axes_plot

sys.path.insert(0, "qd/util")
from set_substrate import set as set_substrate
sys.path.insert(0, "qd/domain/nsg_cppn")
from genome import CPPNGenome
sys.path.insert(0, "qd/domain/utils")
import fitness_function

# Functions for API calls to GIS, machine learning models and optimization services
def load_geodata(coordinates):
    # Mocking a delay for data retrieval
    time.sleep(0)
    return f"Mocked GIS data for area with coordinates: {coordinates}"

def run_optimization(progress_callback=None):
    config_file = f'qd/config/cppn/cfg.yml'
    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    str_current_datetime = str(current_datetime)

    output_path = f'results/{str_current_datetime}/'
    print(f'Outputting results to path: {output_path}')
    if not os.path.exists(output_path):
        os.mkdir(output_path)
    shutil.copyfile(config_file, f'{output_path}/cfg.yml')

    genome_config: Dict = yaml.safe_load(open(config_file))
    genome_config["substrate"] = set_substrate(genome_config)
    genome_config["alg"]["substrate_length"] = genome_config["substrate"].shape[0]
    genome_template = CPPNGenome(genome_config)

    labels = genome_config["alg"]["labels"]
    feat_ranges = genome_config.get("alg").get("feat_ranges")
    feat_ranges = np.array(feat_ranges)
    feat_ranges = feat_ranges.T
    cfg_features = genome_config["alg"]["features"]

    dims = [genome_config["alg"]["num_niches"]] * (len(labels))    
    
    nb_cpus = psutil.cpu_count(logical=True)
    print(f'Running on {nb_cpus} CPU cores')
    pool = multiprocessing.Pool(processes=nb_cpus)

    # Height map width/length l
    l = genome_config["solution"]["num_grid_cells"]
    # Define the search space and archive
    working_archive = GridArchive(
        solution_dim=genome_template.get_dimension()[0],
        dims=dims,
        ranges = feat_ranges,
        learning_rate=genome_config["alg"]["learning_rate"],
        threshold_min=0.0,
        extra_fields = {'heightmaps': ((l*l,), np.float32)}
    )

    result_archive = GridArchive(
        solution_dim=genome_template.get_dimension()[0],
        dims=dims,
        ranges = feat_ranges,
        extra_fields = {'heightmaps': ((l*l,), np.float32)}
    )

    emitters = [
        EvolutionStrategyEmitter(
            working_archive,
            x0=[genome_config["alg"]["mu"]] * genome_template.get_dimension()[0],
            sigma0=genome_config["alg"]["sigma"],
            ranker="imp",
            selection_rule="mu",
            restart_rule="basic",
            batch_size = genome_config["alg"]["batch_size"],
            es="sep_cma_es",
        ) for _ in range(genome_config["alg"]["num_emitters"])
    ]

    scheduler = Scheduler(working_archive, emitters, result_archive=result_archive)

    # Run the optimization
    stats = []
    for itr in range(genome_config["alg"]["num_generations"]):
        if itr%genome_config["alg"]["output_inv_frequency"] == 0:
            print(f'Generation: {itr}')
        solutions = scheduler.ask()

        # fitness_function returns: fitness, features, phenotypes, phenotypes_heightmaps, raw_features
        async_results = [pool.apply_async(fitness_function.ribs_eval_cppn, args=(sol, genome_template, genome_config, genome_config["alg"]["mu"], genome_config["alg"]["sigma"])) for sol in solutions]
        results = [ar.get() for ar in async_results]
        results = np.squeeze(np.array(results))

        num_features = feat_ranges.shape[0]
        heightmaps = results[:,num_features+1:]
        scheduler.tell(results[:,0], results[:,1:num_features+1], heightmaps=heightmaps)
        
        stats.append(result_archive.stats)

        # Call the progress callback if provided
        if progress_callback:
            progress_callback(itr + 1, genome_config["alg"]["num_generations"])

        if itr%genome_config["alg"]["output_inv_frequency"]==0 or itr==genome_config["alg"]["num_generations"]-1:
            with open(f'{output_path}archive.pkl', 'wb') as output:
                pickle.dump(result_archive, output)
            
            with open(f'{output_path}stats.pkl', 'wb') as output:
                pickle.dump(stats, output)
            
            print(f'QD score: {result_archive.stats.qd_score}')
            print(f'Coverage: {result_archive.stats.coverage}')

    return result_archive, [labels[i] for i in cfg_features]

def archive_to_2d(archive, measures = [0, 1]):
    pass


def predict_airflow(selected_design):
    # Generate airflow data influenced by the design
    base_airflow = np.random.rand(100, 100)
    influence = np.sin(np.linspace(0, np.pi, 100))[:, None] * np.cos(np.linspace(0, np.pi, 100))[None, :]
    
    influenced_airflow = base_airflow + influence * selected_design
    return influenced_airflow

def cluster_designs(design_data):
    return np.random.randint(0, 3, size=(10,))
