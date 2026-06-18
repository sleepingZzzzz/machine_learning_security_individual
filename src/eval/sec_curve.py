"""Security evaluation curve plotting."""

from pathlib import Path

import matplotlib.pyplot as plt


def plot_security_curves(
    results: dict[str, dict[str, list[float]]],
    epsilons: list[float],
    out_path: Path,
    title: str = "Security Evaluation Curves",
) -> None:
    """
    Plot robust accuracy vs epsilon.

    Args:
        results: {model_name: {attack_name: [accuracies per epsilon]}}
        epsilons: epsilon values
        out_path: path to save PNG
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    for model_name, attacks in results.items():
        for attack_name, accs in attacks.items():
            label = f"{model_name} / {attack_name}"
            ax.plot(epsilons, accs, marker="o", label=label)

    ax.set_xlabel("epsilon (Linf)")
    ax.set_ylabel("Robust Accuracy")
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
