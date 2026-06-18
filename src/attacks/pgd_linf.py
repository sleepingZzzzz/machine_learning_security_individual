"""Projected Gradient Descent under L-infinity constraint."""

import torch
import torch.nn as nn


def pgd_linf(
    model: nn.Module,
    x: torch.Tensor,
    y: torch.Tensor,
    eps: float,
    *,
    steps: int = 20,
    step_size: float | None = None,
    random_start: bool = True,
) -> torch.Tensor:
    """
    PGD-Linf attack on input tensor x in [0, 1].

    Args:
        model: classifier (expects normalized input if normalize_fn provided externally)
        x: clean images, shape (B, C, H, W), values in [0, 1]
        y: ground-truth labels
        eps: Linf budget
        steps: number of PGD iterations
        step_size: gradient step size (default eps/4)
        random_start: random init within Linf ball

    Returns:
        Adversarial examples x_adv in [0, 1], same shape as x.
    """
    if eps <= 0:
        return x.detach().clone()

    step_size = step_size if step_size is not None else eps / 4.0

    x_adv = x.detach().clone()
    if random_start:
        x_adv = x_adv + torch.empty_like(x_adv).uniform_(-eps, eps)
        x_adv = x_adv.clamp(0.0, 1.0)

    for _ in range(steps):
        x_adv.requires_grad_(True)
        logits = model(x_adv)
        loss = nn.CrossEntropyLoss()(logits, y)
        grad = torch.autograd.grad(loss, x_adv)[0]

        x_adv = x_adv.detach() + step_size * grad.sign()
        delta = (x_adv - x).clamp(-eps, eps)
        x_adv = (x + delta).clamp(0.0, 1.0)

    return x_adv.detach()
