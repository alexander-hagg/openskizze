"""Class MAP-Elites."""

import copy
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd

from ...templates.archive import Archive
from ...templates.genome import Genome
from ....file_manager.file_manager import (
    get_archive_fitness_file_path,
    get_coverage_over_generation_file_path,
    get_diversity_file_path,
    get_fitness_file_path,
    get_maps_file_path,
    get_qd_score_file_path,
    get_raw_archive_name,
    get_raw_multiencoding_composition_table_name,
    get_raw_table_name,
)


class MapElitesArchive(Archive):
    """Class MAP-Elites."""

    def __init__(self, config: Dict, seed):
        """
        Initialize the archive.

        Args:
            config (dict): Parameters of the experiment.

            config (dict): Parameters of the MAP-Elites.
        """
        self.config = config
        self.seed = seed
        self.edges = []
        self.res = []

        for _ in range(len(self.config.get("algorithm_parameters").get("features"))):
            self.edges.append(
                np.linspace(0, 1, self.config.get("algorithm_parameters").get("resolution") - 1)
            )
            self.res.append(self.config.get("algorithm_parameters").get("resolution"))

        self.total_niches = self.config.get("algorithm_parameters").get("resolution") ** len(
            self.config.get("algorithm_parameters").get("features")
        )
        self.fitness = np.full(self.res, np.nan)
        self.genes = np.full(self.res, Genome)
        self.features = np.full(self.res, np.nan)
        self.features = np.expand_dims(self.features, 2)
        self.features = np.tile(
            self.features, (1, 1, len(self.config.get("algorithm_parameters").get("features")))
        )

    def update(self, fitness: npt.NDArray, features: npt.NDArray, genes: npt.NDArray) -> float:
        """
        Update the archive with the new individuals.

        Args:
            fitness (npt.NDArray): The fitness of the individuals.

            features (npt.NDArray): The features of the individuals.

            genes (npt.NDArray): The genes of the individuals.

        Returns:
            float: improvement.
        """
        bin_assignment = np.empty((0, fitness.shape[1]), int)
        for i in range(len(self.config.get("algorithm_parameters").get("features"))):
            these_bins = np.digitize(features[:, i], self.edges[i])
            bin_assignment = np.vstack((bin_assignment, these_bins))

        # Find the highest fitness per bin
        # Sort bins by fitness, then by bin coordinates
        bin_fitness = np.vstack([bin_assignment, fitness])
        num_features = bin_assignment.shape[0]
        idx = (-1 * bin_fitness[num_features, :]).argsort()
        bin_fitness = bin_fitness[:, idx]
        for f in range(num_features - 1, -1, -1):
            idy = bin_fitness[f, :].argsort(kind="mergesort")
            bin_fitness = bin_fitness[:, idy]
            idx = idx[idy]
        unq, ind = np.unique(bin_fitness[0:2, :], return_inverse=False, return_index=True, axis=1)
        best_index = idx[ind]
        best_bin = bin_assignment[:, best_index]

        # Get replacement IDs in both Archive and candidate arrays
        replaced = []
        replacement = []

        for f in range(len(best_index)):
            bin_fitness = self.fitness[best_bin[0, f], best_bin[1, f]]
            if np.isnan(bin_fitness) or bin_fitness < fitness[0][best_index[f]]:
                replacement.append(best_index[f])
                replaced.append([best_bin[0, f], best_bin[1, f]])

        # Replace and add to Archive
        for f in range(len(replacement)):
            self.fitness[replaced[f][0], replaced[f][1]] = fitness[0][replacement[f]]
        for f in range(len(replacement)):
            self.features[replaced[f][0], replaced[f][1], :] = features[replacement[f], :]
        for f in range(len(replacement)):
            self.genes[replaced[f][0], replaced[f][1]] = genes[replacement[f]]

        improvement = 100 * len(replaced) / self.total_niches
        return improvement

    @staticmethod
    def get_list_of_empties(pool):
        """Get list of empty cells."""
        empties = [
            False if isinstance(individual, Genome) else True for individual in pool.flatten()
        ]
        return empties

    def create_pool(self) -> npt.NDArray:
        """
        Create a pool of genes.

        Returns:
            npt.NDArray: list of genes
        """
        pool = copy.deepcopy(self.genes)
        pool = pool.reshape((pool.shape[0] * pool.shape[1], 1))
        empties = self.get_list_of_empties(pool)
        # Remove empty genomes

        pool = np.delete(pool, np.where(empties), axis=0)
        pool = pool.flatten()
        return pool

    def create_children(self) -> List[object]:
        """
        Randomly select parents and copy to children and mutate them.

        Returns:
            List[object]: children.
        """
        pool = self.create_pool()

        selection = np.random.randint(
            0, pool.shape[0], self.config.get("algorithm_parameters").get("num_children")
        )
        children = np.take(pool, selection, axis=0)
        children = np.squeeze(children).tolist()

        # Mutate children
        for child in children:
            child.mutate()

        return children

    def get_niches(self) -> npt.NDArray:
        """
        Get the niches.

        Returns:
            np.column_stack(np.where(non_ans)).
        """
        non_ans = np.invert(np.isnan(self.fitness))
        return np.column_stack(np.where(non_ans))


class WrappedMapElitesArchive(MapElitesArchive):
    """Map elites with monitoring functions and saving."""

    def __init__(self, config: Dict, seed):
        """Initialize the class."""
        MapElitesArchive.__init__(self, config, seed)
        self.fitness_over_generations: list = []
        self.qd_score_over_generations: list = []
        self.pure_diversity_over_generations: list = []
        self.coverage_over_generation: list = []
        self.multiencoding_composition = pd.DataFrame()

    def save_results(self) -> None:
        """
        Save the results of the experiment.

        Returns:
            None.
        """
        if self.config.get("method") == "me":
            mut_prob = None
        else:
            mut_prob = self.config.get("methods").get(self.config["method"]).get("mut_probability")
        data = {
            "method": self.config["method"],
            "name": self.config["name"],
            "seed": self.seed,
            "algorithm": self.config["algorithm"],
            "number of generations": self.config.get("algorithm_parameters").get("num_gens"),
            "number of initial population": self.config.get("algorithm_parameters").get(
                "init_samples"
            ),
            "dimension": None
            if self.config.get("method") == "me"
            else self.get_dimension_of_individual_genotype(),
            "mutation probability": mut_prob,
            "fitness": self.fitness_over_generations[-1],
            "qd_score": self.qd_score_over_generations[-1],
            "sum_of_diversity": self.pure_diversity_over_generations[-1],
            "coverage": self.get_coverage(),
        }

        results = pd.DataFrame(data, index=[self.seed])

        results.to_pickle(get_raw_table_name(self.config, self.seed))
        self.save_pure_diversity_over_generation()
        self.save_average_accuracy_over_generation()
        self.save_coverage_over_generation()
        with open(get_raw_archive_name(self.config, self.seed), "wb") as f:
            np.save(f, self.genes)

        self.save_maps()
        self.save_fitness()

    def save_maps(self):
        """Save the height maps of the individuals in the archive."""
        pool = copy.deepcopy(self.genes)
        maps = np.empty_like(pool)
        for i, rows in enumerate(pool):
            for j, individual in enumerate(rows):
                if isinstance(individual, Genome):
                    maps[i, j] = individual.express(as_height_map=True)
        file_path = get_maps_file_path(self.config, self.seed)
        np.save(file_path, maps)

    def save_fitness(self):
        """Save the fitness of the individuals in the archive."""
        file_path = get_archive_fitness_file_path(self.config, self.seed)
        np.save(file_path, self.fitness)

    def get_coverage(self) -> float:
        """
        Compute the coverage of the archive in range [0,1].

        Returns:
            float: coverage of the archive.
        """
        pool = copy.deepcopy(self.genes)
        pool = pool.reshape((pool.shape[0] * pool.shape[1], 1))
        empties = self.get_list_of_empties(pool)
        coverage = 1 - (float(sum(empties)) / len(empties))
        return coverage

    def get_dimension_of_individual_genotype(self) -> int:
        """
        Compute the dimension of the genotype.

        Returns:
            int: The dimension of the genotype encoding.
        """
        individual: Genome = self.create_pool()[0]
        dimension: int = individual.get_dimension()
        return dimension

    def plot(self, ucb_plot: bool = False) -> object:
        """
        Plot help function.

        Args:
            ucb_plot (Bool): set label as Upper confidence bound.

        Returns:
            object: plt.
        """
        plt.clf()
        plt.imshow(self.fitness, cmap="plasma")
        plt.xlabel(
            self.config.get("algorithm_parameters").get("labels")[
                self.config.get("algorithm_parameters").get("features")[0]
            ]
        )
        plt.ylabel(
            self.config.get("algorithm_parameters").get("labels")[
                self.config.get("algorithm_parameters").get("features")[1]
            ]
        )
        cbar = plt.colorbar()
        if not ucb_plot:
            cbar.set_label(self.config.get("algorithm_parameters").get("labels")[-1])
        else:
            cbar.set_label("Upper confidence bound")
        plt.show()
        return plt

    def save_pure_diversity_over_generation(self) -> None:
        """Save the array pure_diversity_over_generations if save_pure_diversity is set to True."""
        if self.config.get("algorithm_parameters").get("save_pure_diversity"):
            file_path = get_diversity_file_path(self.config, self.seed)
            np.save(
                file_path,
                np.asarray(self.pure_diversity_over_generations),
            )

    def save_coverage_over_generation(self) -> None:
        """Save the array coverage_over_generation if save_coverage_over_generation is set to True."""
        if self.config.get("algorithm_parameters").get("save_coverage_over_generation"):
            file_path = get_coverage_over_generation_file_path(self.config, self.seed)
            np.save(
                file_path,
                np.asarray(self.coverage_over_generation),
            )

    def track_average_fitness(self) -> None:
        """Compute the mean fitness in the archive, and store to fitness_over_generations."""
        if self.config.get("algorithm_parameters").get("save_average_accuracy"):
            self.fitness_over_generations.append(np.nanmean(self.fitness).item())
            self.qd_score_over_generations.append(np.nansum(self.fitness).item())

    def track_coverage(self) -> None:
        """Compute the mean fitness in the archive, and store to fitness_over_generations."""
        if self.config.get("algorithm_parameters").get("save_coverage_over_generation"):
            self.coverage_over_generation.append(self.get_coverage())

    def save_average_accuracy_over_generation(self):
        """Save the average accuracy to the path determined in the config file."""
        if self.config.get("algorithm_parameters").get("save_average_accuracy"):
            file_path_average_fitness = get_fitness_file_path(self.config, self.seed)
            np.save(file_path_average_fitness, np.asarray(self.fitness_over_generations))
            file_path_qd_score = get_qd_score_file_path(self.config, self.seed)
            np.save(file_path_qd_score, np.asarray(self.qd_score_over_generations))

    def compute_average_pure_diversity(self) -> None:
        """
        Measure the sum of all L-0.1 Norm between all the pairs of individuals in the archive.

        Append it  to self.pure_diversity_over_generations.
        """
        if self.config.get("algorithm_parameters").get("save_pure_diversity"):
            pool = self.create_pool()
            n_samples = len(pool)
            height_maps = [pool[i].express(as_height_map=True).flatten() for i in range(n_samples)]
            pure_diversity = [
                np.linalg.norm((height_maps[i] - height_maps[j]), ord=0.1)
                for i in range(len(pool) - 1)
                for j in range(i, len(pool))
            ]
            self.pure_diversity_over_generations.append(np.asarray(pure_diversity).sum())

    def track_multi_encoding_composition(self, gen: int) -> None:
        """
        Track the participation in the archive by the different encodings.

        Args:
            gen (int): The current generation.
        """
        pool = self.create_pool()
        names = [type(individual).__name__ for individual in pool]
        labels, counts = np.unique(names, return_counts=True)
        composition_at_current_generation = pd.DataFrame(columns=labels)
        composition_at_current_generation.loc[0] = counts
        composition_at_current_generation["generation"] = gen
        self.multiencoding_composition = self.multiencoding_composition.append(
            composition_at_current_generation
        )

    def save_multi_encoding_composition(self):
        """Save the information about the participation in the archive over generations."""
        file_path_multiencondig_composition = get_raw_multiencoding_composition_table_name(
            self.config, self.seed
        )
        self.multiencoding_composition.to_csv(
            file_path_multiencondig_composition, na_rep=0, index=False
        )
