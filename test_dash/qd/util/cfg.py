"""Load the YAML file with the parameters of the archive."""
from typing import Dict

import yaml


def get(path_to_conf: str) -> Dict:
    """
    Get the parameters for the archive.

    Args:
        path_to_conf (str): Path to the YAML file containing the parameters for the archive.

    Returns:
        Dict: The parameters of the archive.

    """
    return yaml.safe_load(open(path_to_conf))
