"""Area Under the Security Evaluation Curve."""

import numpy as np

# numpy>=2.0 renamed trapz -> trapezoid; keep both for compatibility.
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


def compute_auc(epsilons: list[float], accuracies: list[float]) -> float:
    """
    Trapezoidal AUC over (epsilon, robust_accuracy).

    Lower AUC => stronger attack (accuracy drops more as epsilon increases).
    """
    if len(epsilons) != len(accuracies):
        raise ValueError("epsilons and accuracies must have same length")
    if len(epsilons) < 2:
        return float(accuracies[0]) if accuracies else 0.0
    return float(_trapz(accuracies, epsilons))
