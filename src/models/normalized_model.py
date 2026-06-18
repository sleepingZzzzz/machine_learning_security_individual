"""Wrap a classifier so PGD operates in [0,1] space while model sees normalized input."""

import torch
import torch.nn as nn
from torchvision import transforms


class NormalizedModel(nn.Module):
    def __init__(self, model: nn.Module, mean: tuple[float, ...], std: tuple[float, ...]):
        super().__init__()
        self.model = model
        self.normalize = transforms.Normalize(mean=mean, std=std)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(self.normalize(x))
