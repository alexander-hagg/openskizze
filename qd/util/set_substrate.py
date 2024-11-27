from PIL import Image
import os.path as path
import numpy as np
from typing import Dict

def set(config: Dict):
    """
    Create the substrate map to indicate where buildings are allowed.

    Args:
        config (Dict): Configuration of the experiment.

    Returns:
        boolean image.
    """
    img = Image.open(
        path.join(
            config.get("file_naming").get("root_input"),
            config.get("file_naming").get("substrate_address"),
        )
    )
    img = img.resize(
        (config.get("solution").get("num_grid_cells"), config.get("solution").get("num_grid_cells"))
    )
    img = np.array(img)
    return img.astype("bool")