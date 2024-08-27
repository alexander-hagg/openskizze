"""Template of the class Archive."""
from abc import ABC, abstractmethod
from typing import Dict


class Archive(ABC):
    """Template of the class Archive."""

    @abstractmethod
    def __init__(self, domain: Dict, config: Dict) -> None:
        """
        Template of the init function of the class Archive.

        Args:
            domain (Dict): Parameters of the Genome.
            config (Dict): Parameters of the Archive.
        """
        self.domain = domain
        self.config = config

    @abstractmethod
    def create_pool(self):
        """Create a pool of individuals."""
        raise NotImplementedError

    @abstractmethod
    def get_niches(self):
        """Get niches."""
        raise NotImplementedError

    @abstractmethod
    def update(self, fitness, features, genes):
        """Update the archive."""
        raise NotImplementedError
