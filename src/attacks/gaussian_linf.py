"""Random Gaussian noise baseline with L-infinity projection."""

import torch


def gaussian_linf_baseline(
    x: torch.Tensor,
    eps: float,
    *,
    variance: float = 0.001,
) -> torch.Tensor:
    """
    Inject Gaussian noise (mean=eps, variance=variance) and project to Linf ball.

    Args:
        x: clean images in [0, 1]
        eps: Linf budget (also used as noise mean per assignment spec)
        variance: Gaussian variance

    Returns:
        Perturbed images in [0, 1].
    """
    if eps <= 0:
        return x.detach().clone()

    noise = torch.randn_like(x) * (variance ** 0.5) + eps
    delta = noise.clamp(-eps, eps)
    return (x + delta).clamp(0.0, 1.0).detach()
