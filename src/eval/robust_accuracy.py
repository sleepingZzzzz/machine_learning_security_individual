"""Robust accuracy computation."""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm


@torch.no_grad()
def accuracy(model: nn.Module, loader: DataLoader, device: torch.device) -> float:
    correct = 0
    total = 0
    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)
        preds = model(images).argmax(dim=1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)
    return correct / max(total, 1)


def robust_accuracy(
    model: nn.Module,
    loader: DataLoader,
    attack_fn,
    device: torch.device,
) -> float:
    """
    Compute accuracy under attack.

    Args:
        model: expects [0,1] input if using NormalizedModel wrapper
        loader: yields (x in [0,1], labels)
        attack_fn: callable (model, x, y) -> x_adv
    """
    correct = 0
    total = 0
    for images, labels in tqdm(loader, desc="robust_acc", leave=False):
        images = images.to(device)
        labels = labels.to(device)
        x_adv = attack_fn(model, images, labels)
        preds = model(x_adv).argmax(dim=1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)
    return correct / max(total, 1)
