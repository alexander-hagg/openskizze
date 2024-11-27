"""Compositional pattern-producing network (CPPN) class definition."""
from typing import Dict, Tuple

import numpy as np
import numpy.typing as npt

from numpy import cos as cos
from numpy import exp as exp
from numpy import sin as sin
from numpy import tanh as tanh

import networkx as nx
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt

class CPPN:
    """Compositional pattern-producing network (CPPN) class definition."""

    def __init__(self, input_dim=2, hidden_layers=[5, 5], output_dim=1):
        """
        Initialize the Compositional pattern-producing network (CPPN).

        Args:
            input_dim (int): Number of input dimensions.
            hidden_layers (List[int]): List containing the number of neurons in each hidden layer.
            output_dim (int): Number of output neurons.
        """
        self.hidden_layers = hidden_layers
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.act_funcs = {
            0: gaussian_1d,
            1: gaussian_nd,
            2: unit,
            3: _tanh,
            4: one,
            5: _sin,
            6: zero,
            7: relu,
            8: sigmoid,
            9: step,
            10: _cos,
        }

        self.activation_indices = []
        self.weights = []

        prev_size = self.input_dim
        for size in self.hidden_layers:
            # +1 for bias weights
            self.weights.append(np.random.randn(prev_size + 1, size))
            self.activation_indices.append(
                np.random.randint(len(self.act_funcs), size=size)
            )
            prev_size = size
            
        # Initialize output layer with bias weights
        self.weights.append(np.random.randn(prev_size + 1, self.output_dim))
        self.activation_indices.append(
            np.random.randint(len(self.act_funcs), size=self.output_dim)
        )  # Using random activation functions for output

    def set_parameters(self, activation_indices, weights) -> None:
        """
        Set the parameters of the CPPN

        Args:
            activation_indices (List[int]): List of activation function indices.
            weights (List[float]): List of weight values.
        """
        # Set activation indices
        for layer_idx in range(len(self.activation_indices)):
            for neuron_idx in range(len(self.activation_indices[layer_idx])):
                self.activation_indices[layer_idx][neuron_idx] = activation_indices.pop(0)

        # Set weights (including bias weights)
        for layer_idx in range(len(self.weights)):
            for neuron_idx in range(self.weights[layer_idx].shape[0]):
                for weight_idx in range(self.weights[layer_idx].shape[1]):
                    self.weights[layer_idx][neuron_idx, weight_idx] = weights.pop(0)       

    def get_parameters(self) -> npt.NDArray:
        """
        Get the parameters of the CPPN as a vector.

        Returns:
            npt.NDArray: The parameters of the CPPN [weights.flatten | activations.flatten].
        """
        flatweights = np.concatenate([arr.flatten() for arr in self.weights])
        flatacts = np.concatenate([arr.flatten() for arr in self.activation_indices])
        return np.concatenate([flatweights, flatacts])

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
        if len(scaled_indices) > 0:  # Check if there are any True values to process
            outputs = self.forward(scaled_indices)
            # Place the outputs back into the grid
            for i, (x, y) in enumerate(true_indices):
                output_grid[x, y] = np.squeeze(outputs[i])

        return output_grid

    def forward(self, coordinates: npt.NDArray) -> npt.NDArray:
        """
        Forward pass through the CPPN.

        Args:
            coordinates (npt.NDArray): Coordinates as input, typically (num_samples, input_dim).

        Returns:
            npt.NDArray: Predicted output.
        """
        output = coordinates
        for layer_idx, (weight, activation_idx) in enumerate(
            zip(self.weights, self.activation_indices)
        ):
            # Append bias term to the output
            bias = np.ones((output.shape[0], 1))
            output = np.hstack([output, bias])  # Shape: (num_samples, prev_size + 1)

            # Linear transformation
            output = np.dot(output, weight)  # Shape: (num_samples, current_layer_size)

            # Apply activation functions
            activation_funcs = [self.act_funcs[idx] for idx in activation_idx]
            # Apply each activation function to its corresponding neuron
            # Vectorized application for efficiency
            activated_output = np.empty_like(output)
            for j, func in enumerate(activation_funcs):
                activated_output[:, j:j+1] = func(output[:, j:j+1])
            output = activated_output

        return output


    def visualize(self, show_weights=True, show_activations=True, figsize=(12, 8), save_path=None):
        """
        Visualize the CPPN graph, including weight values and activation functions.

        Args:
            show_weights (bool): Whether to display weight values on edges.
            show_activations (bool): Whether to display activation functions on nodes.
            figsize (tuple): Size of the matplotlib figure.
            save_path (str): If provided, the plot will be saved to this path instead of displayed.
        """
        # Initialize the graph
        G = nx.DiGraph()

        # Define layers
        layers = ['Input'] + [f'Hidden {i+1}' for i in range(len(self.hidden_layers))] + ['Output']
        layer_sizes = [self.input_dim] + self.hidden_layers + [self.output_dim]

        # Positioning variables
        pos = {}
        layer_gap = 3
        neuron_gap = 1
        bias_offset = 0.5  # Offset for bias nodes

        # Add nodes layer by layer
        node_labels = {}
        activation_labels = {}
        bias_nodes = []

        current_layer = 0
        y_offset = 0

        for layer_name, size in zip(layers, layer_sizes):
            for neuron in range(size):
                node_id = f'{layer_name}_Neuron_{neuron}'
                G.add_node(node_id)
                # Assign positions
                pos[node_id] = (current_layer * layer_gap, y_offset + neuron * neuron_gap)
                # Activation function label
                if layer_name == 'Input':
                    activation = 'Input'
                else:
                    act_idx = self.activation_indices[current_layer - 1][neuron]
                    activation = self.act_funcs[act_idx].__name__
                activation_labels[node_id] = activation
            # Add bias node for this layer except the output layer
            if layer_name != 'Output':
                bias_id = f'{layer_name}_Bias'
                G.add_node(bias_id)
                pos[bias_id] = (current_layer * layer_gap + 0.5, y_offset + size * neuron_gap / 2)
                activation_labels[bias_id] = 'Bias'
                bias_nodes.append(bias_id)
            current_layer += 1

        # Connect nodes with weights
        current_layer = 0
        for layer_idx in range(len(layers) - 1):
            source_layer = layers[layer_idx]
            target_layer = layers[layer_idx + 1]
            source_size = layer_sizes[layer_idx]
            target_size = layer_sizes[layer_idx + 1]

            # Source neurons
            for src in range(source_size):
                src_id = f'{source_layer}_Neuron_{src}'
                for tgt in range(target_size):
                    tgt_id = f'{target_layer}_Neuron_{tgt}'
                    weight = self.weights[layer_idx][src, tgt]
                    G.add_edge(src_id, tgt_id, weight=weight)

            # Bias connections
            bias_id = f'{source_layer}_Bias'
            for tgt in range(target_size):
                tgt_id = f'{target_layer}_Neuron_{tgt}'
                weight = self.weights[layer_idx][-1, tgt]  # Last row is bias weight
                G.add_edge(bias_id, tgt_id, weight=weight)

            current_layer += 1

        # Create labels
        labels = {}
        for node in G.nodes():
            if show_activations and node in activation_labels:
                labels[node] = f'{node}\n({activation_labels[node]})'
            else:
                labels[node] = node

        # Create edge labels
        edge_labels = {}
        if show_weights:
            for u, v, data in G.edges(data=True):
                weight = data['weight']
                edge_labels[(u, v)] = f"{weight:.2f}"

        # Define node colors
        node_colors = []
        for node in G.nodes():
            if 'Bias' in node:
                node_colors.append('lightgray')
            elif 'Input' in node:
                node_colors.append('lightblue')
            elif 'Output' in node:
                node_colors.append('lightgreen')
            else:
                node_colors.append('white')

        # Draw the graph
        plt.figure(figsize=figsize)
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=700, edgecolors='black')
        nx.draw_networkx_edges(G, pos, arrows=True, arrowstyle='->', arrowsize=20, edge_color='gray')

        # Draw labels
        nx.draw_networkx_labels(G, pos, labels, font_size=8)

        # Draw edge labels
        if show_weights:
            nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=6)

        plt.axis('off')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, format='PNG')
            plt.close()
            print(f"CPPN visualization saved to {save_path}")
        else:
            plt.show()




def gaussian_1d(x: npt.NDArray) -> npt.NDArray:
    """
    1D Gaussian Kernel applied to each input dimension separately and then summed.

    Args:
        x (npt.NDArray): Input values, typically representing the combined input coordinates (shape: num_samples, input_dim).

    Returns:
        npt.NDArray: Gaussian output computed by summing Gaussian contributions from each input dimension.
    """
    # x is expected to be 2D with shape (num_samples, input_dim)
    # Compute the Gaussian for each input dimension separately
    gaussians = np.exp(-0.5 * x**2)  # Apply Gaussian independently to each element in x
    # Sum the individual Gaussian responses across each input dimension
    return np.sum(gaussians, axis=-1, keepdims=True)

def gaussian_nd(x: npt.NDArray) -> npt.NDArray:
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