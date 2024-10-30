"""Fix the seed of the pseudorandom number generator for Numpy."""
import numpy as np


def set_deterministic(seed: int) -> None:
    """
    Seed the Numpy random number generator.

    Args:
        seed (int): Selected seed.
    """
    np.random.seed(seed)
