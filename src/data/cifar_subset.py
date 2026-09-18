"""Balanced CIFAR-10 test subset (deterministic), yielding [0,1] tensors.

Supplementary dataset for the cross-dataset generalization check. The CIFAR-10
test set is already 1000/class; we draw a deterministic balanced subset
(``per_class`` images per class, fixed seed) so the evaluated set is reproducible.
RobustBench CIFAR-10 models take [0,1] 32x32 input, so we only apply ToTensor.
"""

from __future__ import annotations

import random
from pathlib import Path

from torch.utils.data import Dataset
from torchvision import transforms
from torchvision.datasets import CIFAR10

from src.config import CIFAR10_DIR, CIFAR10_PER_CLASS, DEFAULT_SEED


class CIFAR10Balanced(Dataset):
    """Deterministic balanced subset of the CIFAR-10 test set ([0,1] tensors)."""

    def __init__(
        self,
        root: Path | str | None = None,
        per_class: int = CIFAR10_PER_CLASS,
        seed: int = DEFAULT_SEED,
    ):
        root = str(root or CIFAR10_DIR)
        self.base = CIFAR10(
            root=root, train=False, download=False, transform=transforms.ToTensor()
        )

        by_class: dict[int, list[int]] = {}
        for idx, label in enumerate(self.base.targets):
            by_class.setdefault(int(label), []).append(idx)

        rnd = random.Random(seed)
        selected: list[int] = []
        for cls in sorted(by_class):
            pool = sorted(by_class[cls])
            k = min(per_class, len(pool))
            selected.extend(sorted(rnd.sample(pool, k)))
        self.selected = selected

    def __len__(self) -> int:
        return len(self.selected)

    def __getitem__(self, i: int):
        return self.base[self.selected[i]]
