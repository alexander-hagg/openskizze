"""Template of class Genome."""
from abc import ABC, abstractmethod
from typing import Dict

import numpy.typing as npt


class Genome(ABC):
    """Template of the class Genome."""

    config: Dict = {}
    genome_len: int

    @abstractmethod
    def __init__(self, config: Dict) -> None:
        """
        Initialize the class Genome.

        Args:
            config (Dict): Parameters of the class Genome.
        """
        self._computed_phenotype = None
        Genome.config = config

    @abstractmethod
    def mutate(self) -> None:
        """Mutate the genome."""
        raise NotImplementedError

    @abstractmethod
    def express(self, as_height_map: bool) -> npt.NDArray:
        """
        Convert the genotype into the phenotype.

        Args:
            as_height_map (bool): return 2.5D map if true, else voxel representation.

        Returns:
            npt.NDArray: The map produced by the individual.
        """
        raise NotImplementedError

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the dimensionality of the representation of the Class."""
        raise NotImplementedError

    @abstractmethod
    def reload_config(self, config):
        """
        Load the experiment parameters to the Class variable config.

        Args
            config: The dictionary containing the experiment parameters.
        """
        raise NotImplementedError

    @property
    def height_map(self):
        """Get the 2.5-dimension map."""
        return self._computed_phenotype

    @height_map.setter
    def height_map(self, phenotype):
        """Set the 2.5-dimension map."""
        self._computed_phenotype = phenotype

    def get_computed_phenotype(self):
        """Get the height map."""
        return self._computed_phenotype
