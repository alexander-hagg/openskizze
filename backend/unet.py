# OpenSKIZZE
# Copyright (C) 2025 [Alexander Hagg]
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
U-NET Architecture for KLAM_21 Spatial Prediction

Predicts 6 KLAM_21 output fields from terrain, buildings, and landuse inputs.
Uses skip connections to preserve spatial details important for flow fields.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class UNetConfig:
    """Configuration for U-NET model."""
    
    # Architecture
    input_channels: int = 3      # terrain, buildings, landuse
    output_channels: int = 6     # Ex, Hx, uq, vq, uz, vz
    base_channels: int = 64      # Channels in first encoder level
    depth: int = 4               # Number of encoder/decoder levels
    dropout: float = 0.1         # Dropout probability
    
    # Input handling
    input_height: int = 66       # Original input height
    input_width: int = 94        # Original input width
    
    @property
    def padded_height(self) -> int:
        """Height padded to be divisible by 2^depth."""
        factor = 2 ** self.depth
        return int(math.ceil(self.input_height / factor) * factor)
    
    @property
    def padded_width(self) -> int:
        """Width padded to be divisible by 2^depth."""
        factor = 2 ** self.depth
        return int(math.ceil(self.input_width / factor) * factor)
    
    @property
    def pad_height(self) -> int:
        """Padding needed for height."""
        return self.padded_height - self.input_height
    
    @property
    def pad_width(self) -> int:
        """Padding needed for width."""
        return self.padded_width - self.input_width


class ConvBlock(nn.Module):
    """Double convolution block: Conv -> BN -> ReLU -> Conv -> BN -> ReLU."""
    
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        dropout: float = 0.0
    ):
        super().__init__()
        
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(out_channels)
        self.dropout = nn.Dropout2d(p=dropout) if dropout > 0 else nn.Identity()
        self.relu = nn.ReLU(inplace=True)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.relu(self.bn1(self.conv1(x)))
        x = self.dropout(x)
        x = self.relu(self.bn2(self.conv2(x)))
        return x


class EncoderBlock(nn.Module):
    """Encoder block: ConvBlock -> MaxPool."""
    
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        dropout: float = 0.0
    ):
        super().__init__()
        self.conv_block = ConvBlock(in_channels, out_channels, dropout)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns (pooled output, skip connection)."""
        skip = self.conv_block(x)
        pooled = self.pool(skip)
        return pooled, skip


class DecoderBlock(nn.Module):
    """Decoder block: Upsample -> Concat skip -> ConvBlock."""
    
    def __init__(
        self,
        in_channels: int,
        skip_channels: int,
        out_channels: int,
        dropout: float = 0.0
    ):
        super().__init__()
        # Bilinear upsampling (avoids checkerboard artifacts)
        self.upsample = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        # Reduce channels after upsampling
        self.conv_reduce = nn.Conv2d(in_channels, out_channels, kernel_size=1)
        # Conv block after concatenation
        self.conv_block = ConvBlock(out_channels + skip_channels, out_channels, dropout)
    
    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.upsample(x)
        x = self.conv_reduce(x)
        x = torch.cat([x, skip], dim=1)
        x = self.conv_block(x)
        return x


class UNet(nn.Module):
    """
    U-NET for KLAM_21 spatial prediction.
    
    Architecture:
        - Encoder: 4 levels with [64, 128, 256, 512] channels
        - Bottleneck: 512 channels
        - Decoder: 4 levels with [256, 128, 64, 64] channels
        - Skip connections between encoder and decoder at each level
        - Output: 6-channel prediction (Ex, Hx, uq, vq, uz, vz)
    
    Input handling:
        - Pads input to dimensions divisible by 16 (for 4-level pooling)
        - Crops output back to original dimensions
    """
    
    def __init__(self, config: UNetConfig):
        super().__init__()
        self.config = config
        
        # Calculate channel sizes for each level
        channels = [config.base_channels * (2 ** i) for i in range(config.depth)]
        # channels = [64, 128, 256, 512] for depth=4, base=64
        
        # Encoder
        self.encoders = nn.ModuleList()
        in_ch = config.input_channels
        for ch in channels[:-1]:  # All but last (bottleneck)
            self.encoders.append(EncoderBlock(in_ch, ch, config.dropout))
            in_ch = ch
        
        # Bottleneck
        self.bottleneck = ConvBlock(channels[-2], channels[-1], config.dropout)
        
        # Decoder
        self.decoders = nn.ModuleList()
        for i in range(config.depth - 2, -1, -1):
            in_ch = channels[i + 1]
            skip_ch = channels[i]
            out_ch = channels[i]
            self.decoders.append(DecoderBlock(in_ch, skip_ch, out_ch, config.dropout))
        
        # Output head
        self.output_conv = nn.Conv2d(channels[0], config.output_channels, kernel_size=1)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights using Kaiming initialization."""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
    
    def _pad_input(self, x: torch.Tensor) -> torch.Tensor:
        """Pad input to dimensions divisible by 2^depth."""
        pad_h = self.config.pad_height
        pad_w = self.config.pad_width
        
        if pad_h > 0 or pad_w > 0:
            # Pad on right and bottom (reflection padding for better boundary handling)
            x = F.pad(x, (0, pad_w, 0, pad_h), mode='reflect')
        
        return x
    
    def _crop_output(self, x: torch.Tensor) -> torch.Tensor:
        """Crop output back to original dimensions."""
        h = self.config.input_height
        w = self.config.input_width
        return x[:, :, :h, :w]
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor (B, 3, H, W) with terrain, buildings, landuse
        
        Returns:
            Output tensor (B, 6, H, W) with Ex, Hx, uq, vq, uz, vz predictions
        """
        # Pad input
        x = self._pad_input(x)
        
        # Encoder with skip connections
        skips = []
        for encoder in self.encoders:
            x, skip = encoder(x)
            skips.append(skip)
        
        # Bottleneck
        x = self.bottleneck(x)
        
        # Decoder with skip connections (reverse order)
        for decoder, skip in zip(self.decoders, reversed(skips)):
            x = decoder(x, skip)
        
        # Output
        x = self.output_conv(x)
        
        # Crop to original size
        x = self._crop_output(x)
        
        return x
    
    def count_parameters(self) -> int:
        """Count total trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
    
    def summary(self) -> str:
        """Return model summary string."""
        lines = [
            "U-NET Model Summary",
            "=" * 50,
            f"Input channels:  {self.config.input_channels}",
            f"Output channels: {self.config.output_channels}",
            f"Base channels:   {self.config.base_channels}",
            f"Depth:           {self.config.depth}",
            f"Dropout:         {self.config.dropout}",
            f"",
            f"Input size:      {self.config.input_height} × {self.config.input_width}",
            f"Padded size:     {self.config.padded_height} × {self.config.padded_width}",
            f"",
            f"Parameters:      {self.count_parameters():,}",
            "=" * 50,
        ]
        return "\n".join(lines)


# ============================================================================
# Loss Functions
# ============================================================================

class MSELoss(nn.Module):
    """Standard MSE loss."""
    
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        return F.mse_loss(pred, target)


class GradientLoss(nn.Module):
    """
    Gradient loss for preserving spatial structure.
    
    Penalizes differences in spatial gradients (Sobel-like) between
    prediction and target. Important for flow field coherence.
    """
    
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        # Horizontal gradient (dx)
        pred_dx = pred[:, :, :, 1:] - pred[:, :, :, :-1]
        target_dx = target[:, :, :, 1:] - target[:, :, :, :-1]
        
        # Vertical gradient (dy)
        pred_dy = pred[:, :, 1:, :] - pred[:, :, :-1, :]
        target_dy = target[:, :, 1:, :] - target[:, :, :-1, :]
        
        loss_dx = F.mse_loss(pred_dx, target_dx)
        loss_dy = F.mse_loss(pred_dy, target_dy)
        
        return loss_dx + loss_dy


class CombinedLoss(nn.Module):
    """
    Combined MSE + Gradient loss.
    
    Args:
        gradient_weight: Weight for gradient loss (0 = pure MSE, 1 = equal weight)
    """
    
    def __init__(self, gradient_weight: float = 0.5):
        super().__init__()
        self.gradient_weight = gradient_weight
        self.mse_loss = MSELoss()
        self.gradient_loss = GradientLoss()
    
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        mse = self.mse_loss(pred, target)
        grad = self.gradient_loss(pred, target)
        return mse + self.gradient_weight * grad


def get_loss_function(loss_type: str, gradient_weight: float = 0.5) -> nn.Module:
    """
    Get loss function by name.
    
    Args:
        loss_type: 'mse' or 'mse_grad'
        gradient_weight: Weight for gradient component (if using mse_grad)
    
    Returns:
        Loss function module
    """
    if loss_type == 'mse':
        return MSELoss()
    elif loss_type == 'mse_grad':
        return CombinedLoss(gradient_weight=gradient_weight)
    else:
        raise ValueError(f"Unknown loss type: {loss_type}. Use 'mse' or 'mse_grad'")


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    # Test model
    config = UNetConfig(
        input_channels=3,
        output_channels=6,
        base_channels=64,
        depth=4,
        input_height=66,
        input_width=94,
    )
    
    model = UNet(config)
    print(model.summary())
    
    # Test forward pass
    x = torch.randn(4, 3, 66, 94)
    y = model(x)
    print(f"\nInput shape:  {x.shape}")
    print(f"Output shape: {y.shape}")
    
    # Test loss functions
    target = torch.randn(4, 6, 66, 94)
    
    mse_loss = get_loss_function('mse')
    mse_grad_loss = get_loss_function('mse_grad', gradient_weight=0.5)
    
    print(f"\nMSE loss: {mse_loss(y, target):.4f}")
    print(f"MSE+Grad loss: {mse_grad_loss(y, target):.4f}")
