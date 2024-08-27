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

from ribs.archives import GridArchive
from ribs.emitters import EvolutionStrategyEmitter
from ribs.schedulers import Scheduler

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

def run_optimization(morph_features):
    num_generations = 10
    num_emitters = 10
    dims = [10, 10, 5, 10]
    mu = 0.0                # Used for initialization, probably want to keep it at 0
    sigma = 2.0             # Used for initialization and mutation
    learning_rate = 0.001
    batch_size = 8
    output_inv_frequency = 10
    cppn_config = [3,3]

    config_file = f'qd/config/cppn/cfg.yml'
    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    str_current_datetime = str(current_datetime)

    output_path = f'results/{str(cppn_config)}_{str_current_datetime}/'
    print(f'Outputting results to path: {output_path}')
    if not os.path.exists(output_path):
        os.mkdir(output_path)
    shutil.copyfile(config_file, f'{output_path}/cfg.yml')

    genome_config: Dict = yaml.safe_load(open(config_file))
    genome_config["methods"]["cppn"]["hidden_layers"] = cppn_config
    genome_config["substrate"] = set_substrate(genome_config)
    genome_config["algorithm_parameters"]["substrate_length"] = genome_config["substrate"].shape[0]
    genome_template = CPPNGenome(genome_config)
    solution_dim, _, _ = genome_template.get_dimension()
    print(f'solution_dim: {solution_dim}')
    labels = genome_config["algorithm_parameters"]["labels"]
    feat_ranges = genome_config.get("algorithm_parameters").get("feat_ranges")
    cfg_features = genome_config["algorithm_parameters"]["features"]

    nb_cpus = psutil.cpu_count(logical=True)
    print(f'Running on {nb_cpus} CPU cores')
    pool = multiprocessing.Pool(processes=nb_cpus)

    # Define the search space and archive
    working_archive = GridArchive(
        solution_dim=solution_dim,
        dims=dims,
        ranges=[(feat_ranges[0][cfg_features[0]],feat_ranges[1][cfg_features[0]]), (feat_ranges[0][cfg_features[1]],feat_ranges[1][cfg_features[1]]), (feat_ranges[0][cfg_features[2]],feat_ranges[1][cfg_features[2]]), (feat_ranges[0][cfg_features[3]],feat_ranges[1][cfg_features[3]])],
        learning_rate=learning_rate,
        threshold_min=0.0,
    )

    result_archive = GridArchive(
        solution_dim=solution_dim,
        dims=dims,
        ranges=[(feat_ranges[0][cfg_features[0]],feat_ranges[1][cfg_features[0]]), (feat_ranges[0][cfg_features[1]],feat_ranges[1][cfg_features[1]]), (feat_ranges[0][cfg_features[2]],feat_ranges[1][cfg_features[2]]), (feat_ranges[0][cfg_features[3]],feat_ranges[1][cfg_features[3]])],
    )

    emitters = []
    emitters.append([
        EvolutionStrategyEmitter(
            working_archive,
            x0=[mu] * solution_dim,
            sigma0=sigma,
            ranker="imp",
            selection_rule="mu",
            restart_rule="basic",
            batch_size = batch_size,
            es="sep_cma_es",
        ) for _ in range(num_emitters)
    ])

    scheduler = Scheduler(working_archive, emitters, result_archive=result_archive)

    # Run the optimization
    stats = []
    for itr in range(num_generations):
        if itr%output_inv_frequency == 0:
            print(f'Generation: {itr}')
        solutions = scheduler.ask()

        async_results = [pool.apply_async(fitness_function.ribs_eval_cppn, args=(sol, genome_template, genome_config, mu, sigma)) for sol in solutions]
        results = [ar.get() for ar in async_results]
        results = np.squeeze(np.array(results))

        scheduler.tell(results[:,0], results[:,1:])

        stats.append(result_archive.stats)

        if itr%output_inv_frequency==0 or itr==num_generations-1:
            with open(f'{output_path}archive.pkl', 'wb') as output:
                pickle.dump(result_archive, output)
            
            with open(f'{output_path}stats.pkl', 'wb') as output:
                pickle.dump(stats, output)
            
            print(f'QD score: {result_archive.stats.qd_score}')
            print(f'Coverage: {result_archive.stats.coverage}')

    # Extract the optimized volume
    # volume = np.zeros((10, 10, 10))
    # for index, solution in zip(archive.as_pandas().index, archive.as_pandas().solution):
    #     x, y = index
    #     volume[x, y, :] = solution[0] * 3  # Scale the solution to height values between 0 and 3

    return result_archive

def predict_airflow(selected_design):
    # Generate airflow data influenced by the design
    base_airflow = np.random.rand(100, 100)
    influence = np.sin(np.linspace(0, np.pi, 100))[:, None] * np.cos(np.linspace(0, np.pi, 100))[None, :]
    
    influenced_airflow = base_airflow + influence * selected_design
    return influenced_airflow

def cluster_designs(design_data):
    return np.random.randint(0, 3, size=(10,))
