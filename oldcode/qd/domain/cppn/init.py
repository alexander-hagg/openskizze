"""Init the CPPN experiment."""
from typing import Any, Dict, List, Tuple

from .genome import CPPNGenome


def do(config: Dict) -> Tuple[Any, List]:
    """
    Initialise the experiment.

    Args:
        config: Dictionary of configuration parameters.

    Returns:
        Tuple[Dict, List[object]]: config, random_pop.
    """
    random_pop = [
        CPPNGenome(config) for _ in range(config.get("algorithm_parameters").get("init_samples"))
    ]

    return config, random_pop
