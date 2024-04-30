"""Evolve."""
import logging
import statistics
from typing import Callable, Dict, List, Tuple

import numpy as np

from .archive import WrappedMapElitesArchive
from ...templates.archive import Archive


def evolve(init: List, config: Dict, ff: Callable, seed: int) -> Tuple[Archive, List]:
    """
    Evolve the archive of MAP-Elites for the number of generations given in the configuration file.

    Args:
        init (List): List of objects which are the initial population.
        config (Dict): MAP-Elites parameters of the experiment.
        config (Dict): The experiment parameters of the config.
        ff (Callable): The fitness function.
        seed (int): seed of the experiment.

    Returns:
        Tuple(object, list) which are the archive and the improvement.
    """
    archive = WrappedMapElitesArchive(config, seed)
    fitness, features = ff.get(init, config)[0:2]
    improvement = [archive.update(fitness, features, init)]

    # Evolution
    for i_gen in range(config.get("algorithm_parameters").get("num_gens")):
        if config.get("method") == "me" and i_gen % 10 == 0:
            archive.track_multi_encoding_composition(i_gen)
        if i_gen % 100 == 0:
            archive.track_average_fitness()
            archive.compute_average_pure_diversity()
            archive.track_coverage()
            logging.info(
                f'Generation: {i_gen}/{config.get("algorithm_parameters").get("num_gens")}'
            )
            if i_gen > 99:
                logging.info(
                    f"Avg. improvement in last 100 gens: {np.around(statistics.mean(improvement[-99:]), 3)} %"
                )
        children = archive.create_children()
        fitness, features = ff.get(children, config)[0:2]
        improvement.append(archive.update(fitness, features, children))

    archive.track_average_fitness()
    archive.save_average_accuracy_over_generation()

    archive.compute_average_pure_diversity()
    archive.save_pure_diversity_over_generation()

    archive.track_coverage()
    archive.save_coverage_over_generation()

    if config.get("method") == "me":
        archive.track_multi_encoding_composition(config.get("algorithm_parameters").get("num_gens"))
        archive.save_multi_encoding_composition()
    return archive, improvement
