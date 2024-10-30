import numpy as np
from typing import Dict
import yaml
import sys
import pickle
import multiprocessing
import psutil
import shutil
from datetime import datetime
import os
import click

from ribs.archives import GridArchive
from ribs.emitters import GaussianEmitter, IsoLineEmitter, EvolutionStrategyEmitter
from ribs.schedulers import Scheduler
import matplotlib.pyplot as plt
from ribs.visualize import parallel_axes_plot

sys.path.insert(0, "util")
from set_substrate import set as set_substrate
sys.path.insert(0, "domain/nsg_cppn")
from genome import CPPNGenome
sys.path.insert(0, "domain/utils")
import fitness_function


def parse_ints(ctx, param, value):
    print(value)
    try:
        return [int(v.strip()) for v in value.split(',')]
    except ValueError:
        raise click.BadParameter('Each part of cppn_config must be an integer.')


@click.command()
@click.option(
    "--num_generations",
    default=25000,
    help="Number of generations to run QD.",
    type=int
)
@click.option(
    "--num_emitters",
    default=30,
    help="Number of QD emitters.",
    type=int
)
@click.option(
    "--batch_size",
    default=10,
    help="Number of children per emitter.",
    type=int
)
@click.option(
    "--dims",
    default="10,10,5,10",
    help="Archive niches per dimension.",
    callback=parse_ints,
    type=str
)
@click.option(
    "--cppn_config",
    default="3,3",
    help="Number of generations to run QD.",
    callback=parse_ints,
    type=str
)
@click.option(
    "--plotting",
    default=False,
    help="Intermediate plotting of QD archive.",
    type=bool
)
@click.option(
    "--output_inv_frequency",
    default=10,
    help="Output frequency (pkl and visualization).",
    type=int
)
@click.version_option()
 
def main(num_generations: int, num_emitters: int, batch_size: int, dims: list, cppn_config: list, plotting: bool, output_inv_frequency: int) -> None:    
    print(f'num_generations: {num_generations}')
    print(f'num_emitters: {num_emitters}')
    print(f'batch_size: {batch_size}')
    print(f'dims: {dims}')
    print(f'cppn_config: {cppn_config}')
    print(f'plotting: {plotting}')
    print(f'output_inv_frequency: {output_inv_frequency}')
    # These configurations are domain-dependent and will be kept the same for this project
    mu = 0.0                # Used for initialization, probably want to keep it at 0
    sigma = 2.0             # Used for initialization and mutation
    learning_rate = 0.001
    

    config_file = f'data/config/cppn/cfg.yml'
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
    
    archives = []
    for i in range(1):
        archives.append(GridArchive(
            solution_dim=solution_dim,
            dims=dims,
            ranges=[(feat_ranges[0][cfg_features[0]],feat_ranges[1][cfg_features[0]]), (feat_ranges[0][cfg_features[1]],feat_ranges[1][cfg_features[1]]), (feat_ranges[0][cfg_features[2]],feat_ranges[1][cfg_features[2]]), (feat_ranges[0][cfg_features[3]],feat_ranges[1][cfg_features[3]])],
            learning_rate=learning_rate,
            threshold_min=0.0,
        ))

    result_archives = []
    for i in range(1):
        result_archives.append(GridArchive(
            solution_dim=solution_dim,
            dims=dims,
            ranges=[(feat_ranges[0][cfg_features[0]],feat_ranges[1][cfg_features[0]]), (feat_ranges[0][cfg_features[1]],feat_ranges[1][cfg_features[1]]), (feat_ranges[0][cfg_features[2]],feat_ranges[1][cfg_features[2]]), (feat_ranges[0][cfg_features[3]],feat_ranges[1][cfg_features[3]])],
        ))

    emitters_meta = []
    emitters_meta.append([
        EvolutionStrategyEmitter(
            archives[0],
            x0=[mu] * solution_dim,
            sigma0=sigma,
            ranker="imp",
            selection_rule="mu",
            restart_rule="basic",
            batch_size = batch_size,
            es="sep_cma_es",
        ) for _ in range(num_emitters)
    ])

    emitter_name = 'SEP-CMA-ES'
    
    if plotting:
        plt.ion()
        fig, (ax1) = plt.subplots(nrows=1, ncols=1, figsize=(25, 5))
    emitters = emitters_meta[0]

    print(f'archives[0]: {archives[0]}')

    scheduler = Scheduler(archives[0], emitters, result_archive=result_archives[0])
    print(f'Running: {emitter_name}')
    
    stats = []
    for itr in range(num_generations):
        if itr%output_inv_frequency == 0:
            print(f'Generation: {itr}')
        solutions = scheduler.ask()

        async_results = [pool.apply_async(fitness_function.ribs_eval_cppn, args=(sol, genome_template, genome_config, mu, sigma)) for sol in solutions]
        results = [ar.get() for ar in async_results]
        results = np.squeeze(np.array(results))

        scheduler.tell(results[:,0], results[:,1:])

        stats.append(result_archives[0].stats)

        if plotting:
            if itr%output_inv_frequency==0 or itr==num_generations-1:
                if itr == 0:
                    parallel_axes_plot(result_archives[0], ax = fig.axes[0], vmin = 0, vmax = 1, sort_archive = True)
                else:
                    fig.axes[0].cla()
                    parallel_axes_plot(result_archives[0], ax = fig.axes[0], vmin = 0, vmax = 1, sort_archive = True, cbar = None)
                fig.axes[0].set_xticklabels([labels[i] for i in cfg_features])
                fig.axes[0].set_title(f'{emitter_name} Emitter')
                plt.draw()
                plt.pause(0.001)
                plt.show(block=False)
        
        if itr%output_inv_frequency==0 or itr==num_generations-1:
            with open(f'{output_path}archive.pkl', 'wb') as output:
                pickle.dump(result_archives[0], output)
            
            with open(f'{output_path}stats.pkl', 'wb') as output:
                pickle.dump(stats, output)
            
            print(f'archive_{emitter_name}_sigma_{sigma}_learning_rate_{learning_rate}')
            print(f'QD score: {result_archives[0].stats.qd_score}')
            print(f'Coverage: {result_archives[0].stats.coverage}')
            


if __name__ == '__main__':
    main()