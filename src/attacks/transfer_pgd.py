"""Transfer-oriented PGD-Linf: MI + DI + TI + CW/margin loss.

These enhancements are applied when crafting adversarial examples on the
*surrogate* model, to improve cross-model (black-box) transferability:

- MI  (Dong et al. 2018): momentum on the (L1-normalized) gradient stabilizes
      the update direction across iterations, yielding more transferable perturbations.
- DI  (Xie et al. 2019): random resize + pad of the input at each step (input
      diversity) prevents over-fitting the perturbation to the surrogate.
- TI  (Dong et al. 2019): convolve the gradient with a fixed Gaussian kernel,
      approximating an attack averaged over translated inputs.
- margin (CW-style): maximize ``max_{k!=y} z_k - z_y`` instead of cross-entropy;
      a decision-boundary-oriented loss that transfers better than CE.

All options degrade gracefully to plain PGD when disabled (momentum=0, di_prob=0,
ti_kernel_size<=1, loss="ce").
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def _ce_loss(logits: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    return F.cross_entropy(logits, y)


def _margin_loss(logits: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """CW-style untargeted margin; ascending it pushes x across the boundary."""
    correct = logits.gather(1, y.unsqueeze(1)).squeeze(1)
    tmp = logits.clone()
    tmp.scatter_(1, y.unsqueeze(1), float("-inf"))
    other = tmp.max(dim=1).values
    return (other - correct).mean()


def _gaussian_kernel(
    kernel_size: int, sigma: float, channels: int, device, dtype
) -> torch.Tensor:
    ax = torch.arange(kernel_size, dtype=dtype, device=device) - (kernel_size - 1) / 2.0
    g1 = torch.exp(-(ax**2) / (2.0 * sigma**2))
    kernel2d = torch.outer(g1, g1)
    kernel2d = kernel2d / kernel2d.sum()
    return kernel2d.expand(channels, 1, kernel_size, kernel_size).contiguous()


def _input_diversity(
    x: torch.Tensor, prob: float, image_size: int, low_ratio: float = 0.9
) -> torch.Tensor:
    """Random resize to [low_ratio*S, S] then random pad back to S, with prob."""
    if prob <= 0 or torch.rand(1).item() >= prob:
        return x
    low = max(1, int(image_size * low_ratio))
    rnd = int(torch.randint(low, image_size + 1, (1,)).item())
    rescaled = F.interpolate(x, size=(rnd, rnd), mode="bilinear", align_corners=False)
    rem = image_size - rnd
    if rem == 0:
        return rescaled
    pad_top = int(torch.randint(0, rem + 1, (1,)).item())
    pad_left = int(torch.randint(0, rem + 1, (1,)).item())
    return F.pad(
        rescaled, [pad_left, rem - pad_left, pad_top, rem - pad_top], value=0.0
    )


def transfer_pgd_linf(
    model: nn.Module,
    x: torch.Tensor,
    y: torch.Tensor,
    eps: float,
    *,
    steps: int = 20,
    step_size: float | None = None,
    random_start: bool = True,
    momentum: float = 0.0,
    di_prob: float = 0.0,
    ti_kernel_size: int = 0,
    ti_sigma: float = 3.0,
    loss: str = "ce",
    image_size: int = 224,
) -> torch.Tensor:
    """Transfer-enhanced PGD-Linf on x in [0,1]. See module docstring for options."""
    if eps <= 0:
        return x.detach().clone()

    step_size = step_size if step_size is not None else eps / 4.0
    loss_fn = _margin_loss if loss == "margin" else _ce_loss

    use_ti = bool(ti_kernel_size) and ti_kernel_size > 1
    kernel = (
        _gaussian_kernel(ti_kernel_size, ti_sigma, x.shape[1], x.device, x.dtype)
        if use_ti
        else None
    )

    x_adv = x.detach().clone()
    if random_start:
        x_adv = (x_adv + torch.empty_like(x_adv).uniform_(-eps, eps)).clamp(0.0, 1.0)

    g = torch.zeros_like(x_adv)
    for _ in range(steps):
        x_adv.requires_grad_(True)
        x_in = _input_diversity(x_adv, di_prob, image_size) if di_prob > 0 else x_adv
        logits = model(x_in)
        loss_val = loss_fn(logits, y)
        grad = torch.autograd.grad(loss_val, x_adv)[0]

        if use_ti:
            grad = F.conv2d(grad, kernel, padding=ti_kernel_size // 2, groups=x.shape[1])

        if momentum > 0:
            grad = grad / grad.abs().sum(dim=(1, 2, 3), keepdim=True).clamp_min(1e-12)
            g = momentum * g + grad
            step_dir = g.sign()
        else:
            step_dir = grad.sign()

        x_adv = x_adv.detach() + step_size * step_dir
        delta = (x_adv - x).clamp(-eps, eps)
        x_adv = (x + delta).clamp(0.0, 1.0)

    return x_adv.detach()
