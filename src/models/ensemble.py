"""Ensemble surrogate: probability-averaged combination of several models.

Averaging in *probability* space (not logits) makes the ensemble robust to the
large logit-scale mismatch between heterogeneous members (e.g. an adversarially
trained CNN vs a robust transformer), so no single member dominates the gradient.

forward() returns ``log(mean_m w_m * softmax(z_m))``. Because the averaged
probabilities already form a valid distribution (sum to 1), feeding this log
into ``F.cross_entropy`` recovers exactly ``-log p_ens[y]`` (an extra log_softmax
is a no-op on a normalized distribution), and a logit-margin on these log-probs
stays monotonic with the ensemble probabilities. Gradients flow to all members.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class EnsembleModel(nn.Module):
    def __init__(self, models: list[nn.Module], weights: list[float] | None = None):
        super().__init__()
        self.models = nn.ModuleList(models)
        n = len(models)
        if weights is None:
            weights = [1.0 / n] * n
        else:
            if len(weights) != n:
                raise ValueError("weights length must match number of models")
            s = float(sum(weights))
            weights = [w / s for w in weights]
        self._weights = weights

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        probs: torch.Tensor | None = None
        for w, m in zip(self._weights, self.models):
            p = F.softmax(m(x), dim=1) * w
            probs = p if probs is None else probs + p
        return torch.log(probs.clamp_min(1e-12))
