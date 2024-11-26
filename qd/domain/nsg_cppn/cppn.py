"""Compositional pattern-producing network (CPPN) class definition."""
from typing import Dict, Tuple

import numpy as np
import numpy.typing as npt

from numpy import cos as cos
from numpy import exp as exp
from numpy import sin as sin
from numpy import tanh as tanh

class CPPN:
    """Compositional pattern-producing network (CPPN) class definition."""

    def __init__(self, input_dim=2, hidden_layers=[5, 5], output_dim=1):
        """
        Initialize the Compositional pattern-producing network (CPPN).

        Args:
            num_neurons (int): Number of neurons per layer.
            num_layers (int): Number of layers in the network.
            sigma (float): Standard deviation for the parameters initialization.
        """
        self.hidden_layers = hidden_layers
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.act_funcs = {
            0: gaussian,
            1: unit,
            2: _tanh,
            3: one,
            4: _sin,
            5: zero,
            6: relu,
            7: sigmoid,
            8: step,
            9: _cos,
        }

        self.activation_indices = []
        self.weights = []
        
        prev_size = self.input_dim
        for size in self.hidden_layers:
            self.weights.append(np.random.randn(prev_size, size))
            self.activation_indices.append(np.random.randint(len(self.act_funcs), size=size))
            prev_size = size
        
        # Initialize output layer with a fixed activation function (e.g., sigmoid scaled)
        self.weights.append(np.random.randn(prev_size, self.output_dim))
        # self.activation_indices.append(np.array([1] * self.output_dim))  # Using sigmoid index for output
        self.activation_indices.append(np.random.randint(len(self.act_funcs), size= self.output_dim))  # Using sigmoid index for output


    def set_parameters(self, activation_indices, weights) -> None:
        """
        Set the parameters of the CPPN
        TODO check size and type of indices and weights, do they match the CPPN's parameters? 
        """
        for i in range(len(self.activation_indices)):
            num_elements = self.activation_indices[i].shape[0]
            for j in range(num_elements):
                self.activation_indices[i][j] = activation_indices.pop(0)
        for i in range(len(self.weights)):
            num_elements = self.weights[i].shape[0]
            for j in range(num_elements):
                self.weights[i][j] = weights.pop(0)

    def get_parameters(self) -> npt.NDArray:
        """
        Get the parameters of the CPPN as vector.

        Returns:
            npt.NDArray: The parameters of the CPPN.
        """

        flatacts = np.concatenate([arr.flatten() for arr in self.activation_indices])
        flatweights = np.concatenate([arr.flatten() for arr in self.weights])
        return np.concatenate([flatweights, flatacts]) # , flatacts, flatweights

    def sample(self, binary_sample_grid) -> npt.NDArray:
        """
        Predict the value in the grid.

        Args:
            binary_sample_grid (ndarray): A grid indicating points to sample.

        Returns:
            npt.NDArray: The phenotype of the individual.
        """
        grid_length = binary_sample_grid.shape[0]
        output_grid = np.zeros([grid_length, grid_length], dtype=float)

        # Find indices where binary_sample_grid is True
        true_indices = np.argwhere(binary_sample_grid)
        # Scale these indices to [-1, 1]
        scaled_indices = 2 * true_indices / grid_length - 1

        # Call forward on all scaled indices at once
        # Assuming forward is modified to accept a batch of inputs and return a batch of outputs
        if len(scaled_indices) > 0:  # Check if there are any True values to process
            outputs = self.forward(scaled_indices)
            # Place the outputs back into the grid
            for i, (x, y) in enumerate(true_indices):
                output_grid[x, y] = np.squeeze(outputs[0])[i]

        return output_grid

    def forward(self, coordinates: npt.NDArray) -> npt.NDArray:
        """
        Predict.

        Args:
            coordinates (npt.NDArray): Coordinates as input, typically (num_samples, input_dim).

        Returns:
            npt.NDArray: Predicted output.
        """
        # Set initial output as coordinates
        output = coordinates

        # Iterate over each layer
        for i, (activation_idx) in enumerate(self.activation_indices):
            # Each layer now only applies an activation function without linear transformation

            # Apply all activation functions for the layer
            activation_funcs = [self.act_funcs[idx] for idx in activation_idx]

            # Apply all activations on the entire vector for each neuron simultaneously
            output = np.array([activation_funcs[j](output) for j in range(len(activation_funcs))]).T

        return output


def gaussian(x: npt.NDArray) -> npt.NDArray:
    """
    Multivariate Gaussian Kernel.

    Args:
        x (npt.NDArray): Input values, typically representing the combined input coordinates.

    Returns:
        npt.NDArray: Gaussian output computed across the magnitude of each coordinate set.
    """
    # x is expected to be 2D with shape (num_samples, input_dim)
    # Compute the sum of squares across each input vector (Euclidean distance squared)
    distance_squared = np.sum(x**2, axis=-1, keepdims=True)
    # Apply Gaussian: return a symmetric response for the entire input vector
    return np.exp(-0.5 * distance_squared)


def sigmoid(x: float) -> float:
    r"""
    Sigmoid function.

    Args:
        x (float): Input value.

    Returns:
        float: \frac{1}{1+e^{(-x)}.

    """
    x = np.sum(x, axis=-1, keepdims=True)
    x_clipped = np.clip(x, -500, 500)
    return 1 / (1 + np.exp(-x_clipped))

def _tanh(x: float) -> int:
    """
    Output tanh.

    Args:
        _ (float): The input value.

    Returns:
        float: tanh.
    """
    x = np.sum(x, axis=-1, keepdims=True)    
    return tanh(x)

def _sin(x: float) -> int:
    """
    Output sin.

    Args:
        _ (float): The input value.

    Returns:
        float: sin.
    """
    x = np.sum(x, axis=-1, keepdims=True)    
    return sin(x)

def _cos(x: float) -> int:
    """
    Output cos.

    Args:
        _ (float): The input value.

    Returns:
        float: cos.
    """
    x = np.sum(x, axis=-1, keepdims=True)    
    return cos(x)


def zero(x: float) -> int:
    """
    Output zero.

    Args:
        _ (float): The input value.

    Returns:
        int: zero.
    """
    x = np.sum(x, axis=-1, keepdims=True)    
    return np.zeros_like(x)


def unit(x: float) -> float:
    """
    Just return the input value

    Args:
        x (float): The input value.

    Returns:
        float: x.
    """
    x = np.sum(x, axis=-1, keepdims=True)    
    return x


def step(x: float) -> int:
    """
    1 if x is larger than 0.

    Args:
        x (float): The input value.

    Returns:
        int: 1 if x>0  else 0.
    """
    x = np.sum(x, axis=-1, keepdims=True)
    return (x > 0).astype(int)


def one(x: float) -> int:
    """
    Output one.

    Args:
        _ (float): The input value.

    Returns:
        int: one.
    """
    x = np.sum(x, axis=-1, keepdims=True)
    return np.ones_like(x)


def relu(x: float) -> float:
    """
    ReLu

    Args:
        x (float): The input value.

    Returns:
        float: x.
    """
    x = np.sum(x, axis=-1, keepdims=True)
    return np.maximum(0, x)

# def exp(x: float) -> float:
#     """
#     exponential function

#     Args:
#         x (float): The input value.

#     Returns:
#         float: x.
#     """
    
#     return np.exp(x)

# def log(x: float) -> float:
#     """
#     logarithmic function

#     Args:
#         x (float): The input value.

#     Returns:
#         float: x.
#     """
    
#     return np.log(x)