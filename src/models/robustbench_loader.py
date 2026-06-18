"""RobustBench model loader and model zoo introspection."""

import torch
import torch.nn as nn

from robustbench.model_zoo import model_dicts
from robustbench.model_zoo.enums import BenchmarkDataset, ThreatModel

from src.config import DATASET, RECOMMENDED_ROBUST_MODELS, THREAT_MODEL


def _dataset_enum() -> BenchmarkDataset:
    return BenchmarkDataset(DATASET)


def _threat_enum() -> ThreatModel:
    return ThreatModel(THREAT_MODEL)


def load_robustbench_model(
    model_name: str,
    device: torch.device | str = "cpu",
) -> nn.Module:
    """
    Load a RobustBench model.

    ImageNet models from the zoo already include input normalization
  (normalize_model with ImageNet mean/std). Feed [0, 1] RGB tensors.
    """
    from robustbench.utils import load_model

    model = load_model(
        model_name=model_name,
        dataset=DATASET,
        threat_model=THREAT_MODEL,
    )
    model = model.to(device)
    model.eval()
    return model


def list_available_models() -> list[str]:
    """Return model names in RobustBench zoo for ImageNet Linf."""
    zoo = model_dicts[_dataset_enum()][_threat_enum()]
    return sorted(zoo.keys())


def list_recommended_robust_models() -> list[str]:
    """Return recommended robust models that exist in the current zoo."""
    available = set(list_available_models())
    return [m for m in RECOMMENDED_ROBUST_MODELS if m in available]
