"""CPPN Genome class definition."""

import sys
from typing import Dict

import numpy as np
import numpy.typing as npt

import cppn

sys.path.insert(0, "domain/utils")
from two_d_map_to_voxel import two_d_map_to_voxel
from templates.genome import Genome

sys.path.insert(0, "util/quadric")

EPSILON = 1e-5


class CPPNGenome(Genome):
    """CPPN Genome class definition."""

    config: Dict = {}

    def __init__(self, config: Dict) -> None:
        """
        Initiate the object of type CPPNGenome.

        Args:
            config (Dict): The experiment configuration.
        """
        Genome.__init__(self, config)
        if not bool(CPPNGenome.config):
            CPPNGenome.config = config
        self.genes = cppn.CPPN(
            CPPNGenome.config.get("methods").get("cppn").get("input_dim"),
            CPPNGenome.config.get("methods").get("cppn").get("hidden_layers"),
        )
        self._computed_phenotype = None

    @staticmethod
    def get_dimension():
        """Compute the dimensionality of the CPPN encoding."""
        num_act = 0
        num_weights = 0
        n_inputs = CPPNGenome.config.get("methods").get("cppn").get("input_dim")
        hidden_layers = CPPNGenome.config.get("methods").get("cppn").get("hidden_layers")
        n_outputs = CPPNGenome.config.get("methods").get("cppn").get("output_dim")
        prev_size = n_inputs
        for size in hidden_layers:
            num_act += size
            num_weights += prev_size * size
            prev_size = size
        num_act += n_outputs
        num_weights += prev_size*n_outputs
        dim = num_act + num_weights
        return dim, num_act, num_weights

    def mutate(self) -> None:
        """Mutate the genes of the individual."""
        with np.nditer(self.genes.activations, op_flags=["readwrite"]) as it:
            for x in it:
                if np.random.random() < CPPNGenome.config.get("methods").get("cppn").get(
                    "mut_probability"
                ):
                    x[...] = np.random.randint(0, len(self.genes.act_funcs) - 1)
        with np.nditer(self.genes.weights, op_flags=["readwrite"]) as it:
            for x in it:
                if np.random.random() < CPPNGenome.config.get("methods").get("cppn").get(
                    "mut_probability"
                ):
                    x[...] = x[...] + np.random.normal(
                        0, CPPNGenome.config.get("methods").get("cppn").get("mut_sigma")
                    )

    def express(self, as_height_map: bool) -> npt.NDArray:
        """
        Generate the phenopype from the genotype.

        Returns:
            npt.NDArray that represent the occupancy of the voxels.
        """
        if self.genes is None:
            return None, None, None
        x_coord = np.arange(0, CPPNGenome.config.get("methods").get("num_grid_cells"), 1)
        y_coord = np.arange(0, CPPNGenome.config.get("methods").get("num_grid_cells"), 1)
        x_coord, y_coord = np.meshgrid(x_coord, y_coord)
        raw_sample = self.genes.sample(CPPNGenome.config["substrate"], CPPNGenome.config)
        if CPPNGenome.config.get("methods").get("cppn").get("scale_cppn_out"):
            ranges = np.max(raw_sample) - np.min(raw_sample)
            if ranges == 0:
                ranges = 1
            two_d_map = (
                CPPNGenome.config.get("methods").get("max_height")
                * (raw_sample - np.min(raw_sample))
                / ranges
            )
        else:
            two_d_map = CPPNGenome.config.get("methods").get("max_height") * raw_sample
            two_d_map = np.floor(two_d_map).astype(int)
            maximum = np.max(two_d_map)
            two_d_map = two_d_map - (maximum - CPPNGenome.config.get("methods").get("max_height"))

        two_d_map *= CPPNGenome.config["substrate"]
        self.height_map = np.clip(
            two_d_map.astype(int), 0, CPPNGenome.config.get("methods").get("max_height")
        )

        if as_height_map:
            return self.height_map
        # Convert to voxels
        voxel = two_d_map_to_voxel(self.height_map, CPPNGenome.config)
        return voxel

    def set_genome(self, activation_indices, weights) -> None:
        """
        Set the genome of the individual
        """
        self.genes.set_parameters(activation_indices, weights)

    def get_genome(self) -> npt.NDArray:
        """
        Get the genome of the individual.

        Returns:
            npt.NDArray: Encoded genome in a vector [activations.flatten | self.weights.flatten].
        """
        g = self.genes.get_parameters()
        # g = np.expand_dims(g, 1)
        return g

    def reload_config(self, config: Dict):
        """
        Reload the config to the class CPPNGenome.

        Args:
            config: The experiment parameters.

        Returns:
            None
        """
        setattr(CPPNGenome, "config", config)
