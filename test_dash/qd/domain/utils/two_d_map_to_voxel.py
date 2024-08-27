"""Help function that convert a 2-D map into 3-D voxel occupancy grid."""
from typing import Dict

import numpy as np
import numpy.typing as npt


def two_d_map_to_voxel(two_d_map: npt.NDArray, domain: Dict) -> npt.NDArray:
    """
    Convert a 2-D map into voxel representation.

    Args:
        two_d_map (npt.NDArray): The height map stored in a 2-D matrix.

        domain (Dict): Parameters of the experiment.

    Returns:
        npt.NDArray: voxel representation.
    """
    voxels = np.zeros(
        [
            domain.get("methods").get("num_grid_cells"),
            domain.get("methods").get("num_grid_cells"),
            domain.get("methods").get("max_height"),
        ]
    )

    for x in range(domain.get("methods").get("num_grid_cells")):
        for y in range(domain.get("methods").get("num_grid_cells")):
            if domain["substrate"][x, y]:
                for z in range(two_d_map[x, y]):
                    voxels[x, y, z] = 1

    return voxels
