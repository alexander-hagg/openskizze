"""CPPN Genome class definition."""

import sys
from typing import Dict

import numpy as np
import numpy.typing as npt

from scipy.ndimage import label
import cppn

sys.path.insert(0, "qd/domain/utils")
from two_d_map_to_voxel import two_d_map_to_voxel
sys.path.insert(0, "qd/templates")
from t_genome import Genome

sys.path.insert(0, "qd/util/quadric")

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
            CPPNGenome.config.get("solution").get("cppn").get("input_dim"),
            CPPNGenome.config.get("solution").get("cppn").get("hidden_layers"),
            CPPNGenome.config.get("solution").get("cppn").get("output_dim"),  # Added output_dim parameter
        )
        self._computed_phenotype = None

    @staticmethod
    def get_dimension():
        """Compute the dimensionality of the CPPN encoding."""
        num_act = 0
        num_weights = 0
        n_inputs = CPPNGenome.config.get("solution").get("cppn").get("input_dim")
        hidden_layers = CPPNGenome.config.get("solution").get("cppn").get("hidden_layers")
        n_outputs = CPPNGenome.config.get("solution").get("cppn").get("output_dim")
        prev_size = n_inputs
        for size in hidden_layers:
            num_act += size
            num_weights += (prev_size + 1) * size  # +1 for bias weights
            prev_size = size
        num_act += n_outputs
        num_weights += (prev_size + 1) * n_outputs  # +1 for bias weights
        dim = num_act + num_weights
        return dim, num_act, num_weights

    def mutate(self) -> None:
        """Mutate the genes of the individual."""
        cppn_config = CPPNGenome.config.get("solution").get("cppn")
        cppn_mut_prob = cppn_config.get("mut_probability")
        cppn_mut_sigma = cppn_config.get("mut_sigma")

        # Mutate activation indices
        with np.nditer(self.genes.activation_indices, op_flags=["readwrite"]) as it:
            for x in it:
                if np.random.random() < cppn_mut_prob:
                    x[...] = np.random.randint(0, len(self.genes.act_funcs))

        # Mutate weights (including biases)
        with np.nditer(self.genes.weights, op_flags=["readwrite"]) as it:
            for x in it:
                if np.random.random() < cppn_mut_prob:
                    x[...] += np.random.normal(0, cppn_mut_sigma)

    def express(self, as_height_map: bool) -> npt.NDArray:
        """
        Generate the phenotype from the genotype.

        Returns:
            npt.NDArray that represent the occupancy of the voxels.
        """
        if self.genes is None:
            return None, None, None
        # print(f'num grid cells {CPPNGenome.config.get("solution").get("num_grid_cells")}')
        x_coord = np.arange(0, CPPNGenome.config.get("solution").get("num_grid_cells"), 1)
        y_coord = np.arange(0, CPPNGenome.config.get("solution").get("num_grid_cells"), 1)
        x_coord, y_coord = np.meshgrid(x_coord, y_coord)
        raw_sample = self.genes.sample(CPPNGenome.config["substrate"])

        # Filter out noise
        structure4 = np.array([ [0, 1, 0],
                                [1, 1, 1],
                                [0, 1, 0]])  # 4-connectivity
        # Convert occupancy grid to binary image (1 for occupied, 0 for free)
        img = (raw_sample > 0).astype(int)

        # Label connected components
        labeled_img, num_labels = label(img, structure=structure4)

        # Define minimum cluster size (number of pixels)
        min_cluster_size = 8  # Example value, adjust as needed

        # Compute the size of each labeled cluster
        # Note: label 0 is the background, so we start counting from label 1
        label_sizes = np.bincount(labeled_img.flatten())

        # Create a mask of labels that meet the minimum size requirement
        # Exclude the background label (label 0)
        valid_labels = np.where(label_sizes >= min_cluster_size)[0]
        valid_labels = valid_labels[valid_labels != 0]
        valid_buildings_mask = np.isin(labeled_img, valid_labels)
        raw_sample = raw_sample * valid_buildings_mask
        

        if CPPNGenome.config.get("solution").get("cppn").get("scale_cppn_out"):
            ranges = np.max(raw_sample) - np.min(raw_sample)
            if ranges == 0:
                ranges = 1
            two_d_map = (
                CPPNGenome.config.get("solution").get("max_height")
                * (raw_sample - np.min(raw_sample))
                / ranges
            )
        else:
            two_d_map = CPPNGenome.config.get("solution").get("max_height") * raw_sample
            two_d_map = np.floor(two_d_map).astype(int)
            maximum = np.max(two_d_map)
            two_d_map = two_d_map - (
                maximum - CPPNGenome.config.get("solution").get("max_height")
            )

        two_d_map *= CPPNGenome.config["substrate"]
        self.height_map = np.clip(
            two_d_map.astype(int),
            0,
            CPPNGenome.config.get("solution").get("max_height"),
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
            npt.NDArray: Encoded genome in a vector [weights.flatten | activations.flatten].
        """
        g = self.genes.get_parameters()
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
