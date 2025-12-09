#!/usr/bin/env python3
# OpenSKIZZE - SVGP Model for GUI Integration
# Copyright (C) 2025 [Alexander Hagg]
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Sparse Variational Gaussian Process (SVGP) Model

This module provides the SVGP model architecture for predicting cold air flux
from building layout genomes. The model uses inducing points for scalability
and a Matérn 2.5 kernel with Automatic Relevance Determination (ARD).

Architecture:
- Input: 62D (60D genome + parcel width + parcel height)
- Kernel: Matérn 2.5 with ARD (62 lengthscales)
- Inducing points: 2000 (optimal from HPO experiments)
- Output: Scalar cold air flux prediction + uncertainty

Performance:
- R² = 0.946 (on optimized training data)
- Spearman ρ ≈ 0.97 (ranking fidelity)
- Prediction speed: <5ms per batch
- 95% CI coverage: ~97% (well-calibrated)

Usage:
    from svgp import SVGPModel, load_svgp_model
    
    # Load pre-trained model
    model, likelihood = load_svgp_model('models/svgp_27m.pth', device='cuda')
    
    # Predict with uncertainty
    model.eval()
    likelihood.eval()
    with torch.no_grad():
        predictions = likelihood(model(X_test))
        mean = predictions.mean
        stddev = predictions.stddev  # Uncertainty estimates
"""

import torch
import gpytorch
from gpytorch.models import ApproximateGP
from gpytorch.variational import CholeskyVariationalDistribution, VariationalStrategy
from typing import Tuple


class SVGPModel(ApproximateGP):
    """
    Sparse Variational Gaussian Process for KLAM_21 surrogate modeling.
    
    Uses variational inference with inducing points for scalability.
    Provides both mean predictions and uncertainty estimates (stddev).
    
    Args:
        inducing_points: Tensor of shape (num_inducing, input_dim)
            Initial locations for inducing points. Typically initialized
            with K-means centroids from training data.
        input_dim: Input dimensionality (default: 62)
            62 = 60 (genome) + 1 (width) + 1 (height)
    
    Forward pass returns:
        MultivariateNormal distribution with mean and covariance
    """
    
    def __init__(self, inducing_points: torch.Tensor, input_dim: int = 62):
        # Variational distribution: Cholesky parameterization for stability
        variational_distribution = CholeskyVariationalDistribution(
            inducing_points.size(0)
        )
        
        # Variational strategy: learn inducing point locations
        variational_strategy = VariationalStrategy(
            self, 
            inducing_points, 
            variational_distribution, 
            learn_inducing_locations=True
        )
        
        super().__init__(variational_strategy)
        
        # Mean function: constant mean (learned)
        self.mean_module = gpytorch.means.ConstantMean()
        
        # Covariance function: Scaled Matérn 2.5 with ARD
        # ARD allows different lengthscales per input dimension
        self.covar_module = gpytorch.kernels.ScaleKernel(
            gpytorch.kernels.MaternKernel(
                nu=2.5,  # Twice differentiable (smoother than nu=1.5)
                ard_num_dims=input_dim,  # Separate lengthscale per dimension
            )
        )
        
    def forward(self, x):
        """
        Forward pass through the GP.
        
        Args:
            x: Input tensor of shape (batch_size, input_dim)
        
        Returns:
            MultivariateNormal distribution with:
            - mean: Predicted cold air flux
            - covariance: Uncertainty estimate
        """
        mean_x = self.mean_module(x)
        covar_x = self.covar_module(x)
        return gpytorch.distributions.MultivariateNormal(mean_x, covar_x)


def load_svgp_model(
    model_path: str,
    device: str = 'cpu'
) -> Tuple[SVGPModel, gpytorch.likelihoods.GaussianLikelihood]:
    """
    Load a pre-trained SVGP model from disk.
    
    Args:
        model_path: Path to saved model checkpoint (.pth file)
        device: Device to load model onto ('cpu' or 'cuda')
    
    Returns:
        model: Loaded SVGPModel in eval mode
        likelihood: GaussianLikelihood in eval mode
    
    Example:
        model, likelihood = load_svgp_model('models/svgp_27m.pth', device='cuda')
        
        # Predict on new data
        model.eval()
        likelihood.eval()
        with torch.no_grad():
            X_test = torch.tensor(test_genomes, dtype=torch.float32, device=device)
            predictions = likelihood(model(X_test))
            mean = predictions.mean.cpu().numpy()
            stddev = predictions.stddev.cpu().numpy()  # Uncertainty
    """
    # Load checkpoint
    checkpoint = torch.load(model_path, map_location=device)
    
    # Extract model configuration
    num_inducing = checkpoint['num_inducing']
    input_dim = checkpoint['input_dim']
    
    # Initialize model with saved inducing points
    inducing_points = checkpoint['inducing_points'].to(device)
    model = SVGPModel(inducing_points, input_dim=input_dim)
    model.load_state_dict(checkpoint['model_state_dict'])
    model = model.to(device)
    model.eval()
    
    # Initialize likelihood
    likelihood = gpytorch.likelihoods.GaussianLikelihood()
    likelihood.load_state_dict(checkpoint['likelihood_state_dict'])
    likelihood = likelihood.to(device)
    likelihood.eval()
    
    return model, likelihood


def predict_with_uncertainty(
    model: SVGPModel,
    likelihood: gpytorch.likelihoods.GaussianLikelihood,
    X: torch.Tensor
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Generate predictions with uncertainty estimates.
    
    Args:
        model: SVGP model in eval mode
        likelihood: Gaussian likelihood in eval mode
        X: Input tensor (batch_size, input_dim) on same device as model
    
    Returns:
        mean: Predicted cold air flux (batch_size,)
        stddev: Uncertainty estimate (batch_size,)
    
    Example:
        mean, stddev = predict_with_uncertainty(model, likelihood, X_test)
        
        # Use for UCB acquisition
        ucb_lambda = 1.0
        fitness_adjusted = mean + ucb_lambda * stddev
    """
    model.eval()
    likelihood.eval()
    
    with torch.no_grad():
        predictions = likelihood(model(X))
        mean = predictions.mean
        stddev = predictions.stddev
    
    return mean, stddev
