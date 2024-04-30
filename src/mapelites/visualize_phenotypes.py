"""Help function visualize phenotypes."""
from typing import Dict

import matplotlib.pyplot as plt
from matplotlib.pyplot import axis, clf, xlabel, ylabel


def plot(archive, express, domain: Dict, config: Dict):
    """
    Plot the archive.

    Args:
        archive (): ToDO.
        express (): ToDO.
        domain ():  Configuration of the experiment.
        config ():  Configuration of the archive.

    Returns:
        object: plot the archive.
    """
    clf()
    if domain["plotscale"]:
        scale = 2 * config["resolution"]
    else:
        scale = 1
    for i in range(archive["genes"].shape[0]):
        for j in range(archive["genes"].shape[1]):
            genome = archive["genes"][i, j, :]
            phenotype = express.express_single(genome, domain)
            if phenotype is not None:
                dx = archive["features"][i, j, 0]
                dy = archive["features"][i, j, 1]
                fitness = archive["fitness"][i, j]
                if fitness > 1.0:
                    fitness = 1.0
                elif fitness < 0.0:
                    fitness = 0.0
                express.visualize_raw(phenotype, [1 - fitness, fitness, 0], dx * scale, dy * scale)
    axis("equal")
    xlabel(domain["labels"][domain["features"][0]])
    ylabel(domain["labels"][domain["features"][1]])

    return plt
