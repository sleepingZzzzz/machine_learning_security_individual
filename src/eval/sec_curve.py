"""Security evaluation curve plotting."""

import math
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


def plot_per_model_panels(
    results: dict[str, dict[str, list[float]]],
    epsilons: list[float],
    out_path: Path,
    *,
    title: str = "Per-model Security Curves",
    surrogate_name: str | None = None,
    surrogate_whitebox: list[float] | None = None,
) -> None:
    """
    One subplot per model (2-column grid), so each defender's curves are readable
    on their own scale instead of being crowded into a single axes.

    When ``surrogate_whitebox`` is provided, it is overlaid as a grey dashed
    reference on every *target* panel — making the core finding visible at a
    glance: PGD crushes the surrogate under white-box, yet barely dents the
    (robust) targets under transfer.
    """
    model_names = list(results.keys())
    n = len(model_names)
    ncols = 2 if n > 1 else 1
    nrows = math.ceil(n / ncols)

    fig, axes = plt.subplots(
        nrows, ncols, figsize=(6 * ncols, 4 * nrows), squeeze=False
    )
    axes_flat = axes.flatten()

    for i, model_name in enumerate(model_names):
        ax = axes_flat[i]
        for attack_name, accs in results[model_name].items():
            ax.plot(epsilons, accs, marker="o", label=attack_name)

        if (
            surrogate_whitebox is not None
            and model_name != surrogate_name
            and len(surrogate_whitebox) == len(epsilons)
        ):
            ref_label = (
                f"{surrogate_name} pgd_whitebox (ref)"
                if surrogate_name
                else "surrogate pgd_whitebox (ref)"
            )
            ax.plot(
                epsilons,
                surrogate_whitebox,
                linestyle="--",
                color="gray",
                label=ref_label,
            )

        ax.set_title(model_name, fontsize=10)
        ax.set_xlabel("epsilon (Linf)")
        ax.set_ylabel("Robust Accuracy")
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7)

    for j in range(n, len(axes_flat)):
        axes_flat[j].axis("off")

    fig.suptitle(title)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
