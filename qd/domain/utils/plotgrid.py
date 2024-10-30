"""Plot the archive."""
import os.path as path
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, "src/optimization/util/quadric-mesh-simplification")


import numpy as np
import numpy.typing as npt
import pyvista as pv
from voxelfuse.mesh import Mesh
from voxelfuse.voxel_model import VoxelModel


def plot(
    phenotypes: List,
    config: Dict,
    features=None,
    fitness=None,
    niches=None,
    raw_features=None,
    filename=None,
    grid_resolution=None,
    output_resolution: Tuple[int, int] = (8192, 6144),
) -> object:
    """
    Plot help function.

    Args:
        phenotypes (List[npt.NDArray]):  List of npt.NDArray that encodes the solutions.
        config (Dict): Experiment parameters.
        features (Any, default = None): The features.
        fitness (Any, default = None): The fitness.
        niches (Any, default = None): The niches.
        raw_features (Any, default = None): Raw features.
        filename (str, default = None): The name of the output file.
        grid_resolution (Any, default = None): The resolution of the grid
        output_resolution (Tuple, default = (8192, 6144)): The output image resolution.

    Returns:
        object: object of class type pyvista.Plotter

    """
    n_shapes = len(phenotypes)
    if niches is not None:
        if grid_resolution is not None:
            n_rows = grid_resolution
            n_cols = grid_resolution
        else:
            n_rows = np.max(niches[:, 0]) + 1
            n_cols = np.max(niches[:, 1]) + 1
    else:
        n_rows = int(np.ceil(np.sqrt(n_shapes)))
        n_cols = n_rows
    shape = (n_rows, n_cols)
    plotter = pv.Plotter(
        off_screen=True,
        window_size=output_resolution,
        shape=shape,
        line_smoothing=True,
        polygon_smoothing=True,
    )
    for i in range(n_shapes):
        if niches is None:
            row = int(np.floor(i / n_rows))
            col = i % n_rows
        else:
            row, col = niches[i]
        if raw_features is not None:
            feature_info = (
                config.get("algorithm_parameters").get("labels")[0]
                + ": "
                + str(round(raw_features[i, 0]))
                + "m²\n"
                + config.get("algorithm_parameters").get("labels")[1]
                + ": "
                + str(round(raw_features[i, 1]))
                + "\n"
                + config.get("algorithm_parameters").get("labels")[2]
                + ": "
                + str(round(raw_features[i, 2]))
                + "m²\n"
                + config.get("algorithm_parameters").get("labels")[3]
                + ": "
                + str(round(raw_features[i, 3]))
                + "m²\n"
            )
        else:
            feature_info = ""

        plotter.subplot(row, col)
        sz = config.get("methods").get("num_grid_cells") / 2
        plotter.add_text(feature_info, font_size=8)

        if np.sum(phenotypes[i]) > 0:
            render_mesh(phenotypes[i], f"{filename}.stl")
            mesh = pv.read(f"{filename}.stl")
            plotter.add_mesh(mesh)

        plane_mesh = pv.Plane(
            center=(sz, sz, 0), direction=(0, 0, -1), i_size=2 * sz, j_size=2 * sz
        )
        # TODO
        sat = pv.read_texture(
            path.join(
                config.get("file_naming").get("root_input"),
                config.get("file_naming").get("map_sat_address"),
            )
        )
        plotter.add_mesh(plane_mesh, texture=sat)
        # clrscale = 10*fitness[0][i]
        # if clrscale > 1.0:
        #     clrscale = 1.0
        # clrscale = fitness[0][i]
        # fitnesscolor = [1-clrscale,clrscale,0.0]
        # plotter.set_background(fitnesscolor, all_renderers=False)
    plotter.link_views()
    plotter.camera_position = [(50, 50, 20), (sz, sz, 0), (0, 0, 1)]
    plotter.show(screenshot=f"{filename}.png")
    return plotter


def render_mesh(phenotype: npt.NDArray, name: str) -> None:
    """
    Generate 3D mesh model from the voxel.

    Args:
        phenotype (npt.NDArray): Voxel representation.

        name (str): Name of the stl file.

    Returns:
        None
    """
    model = VoxelModel(phenotype)  # , generateMaterials(4)  4 is aluminium.
    mesh = Mesh.fromVoxelModel(model)
    mesh.export(name)
