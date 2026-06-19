"""Main entry point: smoke test and full security evaluation."""

from __future__ import annotations

import argparse
import csv
import tempfile
import time
from functools import partial
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.attacks.gaussian_linf import gaussian_linf_baseline
from src.attacks.pgd_linf import pgd_linf
from src.attacks.transfer_pgd import transfer_pgd_linf
from src.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_N_SAMPLES,
    DI_PROB,
    EPSILONS,
    GAUSSIAN_VARIANCE,
    IMAGE_SIZE,
    MI_MOMENTUM,
    PGD_RANDOM_START,
    PGD_STEPS,
    ROBUST_MODEL_NAME,
    STANDARD_MODEL_NAME,
    SURROGATE_MODEL_NAME,
    TARGET_MODEL_NAMES,
    TI_KERNEL_SIZE,
    TI_SIGMA,
    TRANSFER_LOSS,
)
from src.data.imagenet_subset import ImageNetSubset, load_indices
from src.data.transforms import get_eval_transform
from src.eval.auc import compute_auc
from src.eval.exp_manager import (
    next_exp_id,
    save_experiment,
    snapshot_hyperparameters,
)
from src.eval.robust_accuracy import accuracy, robust_accuracy
from src.eval.sec_curve import plot_per_model_panels, plot_security_curves
from src.models.robustbench_loader import (
    list_available_models,
    list_recommended_robust_models,
    load_robustbench_model,
)


def _tensor_dataset(subset: ImageNetSubset, max_n: int | None = None):
    """Apply eval transform (to [0,1] tensor) and yield (tensor, label)."""
    tfm = get_eval_transform()
    indices = subset.indices[:max_n] if max_n else subset.indices
    tensors, labels = [], []
    for row in indices:
        from PIL import Image

        path = subset.image_dir / f"{row.image_id}.JPEG"
        img = Image.open(path).convert("RGB")
        tensors.append(tfm(img))
        labels.append(row.class_idx)
    return torch.stack(tensors), torch.tensor(labels, dtype=torch.long)


class TensorDataset(torch.utils.data.Dataset):
    def __init__(self, xs: torch.Tensor, ys: torch.Tensor):
        self.xs = xs
        self.ys = ys

    def __len__(self):
        return len(self.ys)

    def __getitem__(self, idx):
        return self.xs[idx], self.ys[idx]


def make_loader(subset: ImageNetSubset, batch_size: int, max_n: int | None = None) -> DataLoader:
    xs, ys = _tensor_dataset(subset, max_n=max_n)
    return DataLoader(TensorDataset(xs, ys), batch_size=batch_size, shuffle=False)


def cmd_list_models() -> None:
    names = list_available_models()
    recommended = list_recommended_robust_models()
    print(f"Available ImageNet Linf models ({len(names)}):")
    for n in names:
        mark = " [recommended robust]" if n in recommended else ""
        mark = " [default standard]" if n == STANDARD_MODEL_NAME else mark
        mark = " [default robust]" if n == ROBUST_MODEL_NAME else mark
        print(f"  - {n}{mark}")
    print(f"\nDefault pair: {STANDARD_MODEL_NAME} (non-robust) + {ROBUST_MODEL_NAME} (robust)")


def evaluate_model(
    model_name: str,
    loader: DataLoader,
    device: torch.device,
    epsilons: list[float],
) -> dict[str, list[float]]:
    # RobustBench ImageNet models already apply ImageNet normalization internally.
    model = load_robustbench_model(model_name, device=device)

    results: dict[str, list[float]] = {"pgd": [], "gaussian": []}

    for eps in epsilons:
        if eps <= 0:
            acc = accuracy(model, loader, device)
            results["pgd"].append(acc)
            results["gaussian"].append(acc)
            continue

        pgd_fn = partial(
            pgd_linf,
            eps=eps,
            steps=PGD_STEPS,
            step_size=eps / 4,
            random_start=PGD_RANDOM_START,
        )
        gauss_fn = lambda m, x, y, e=eps: gaussian_linf_baseline(x, e, variance=GAUSSIAN_VARIANCE)

        results["pgd"].append(robust_accuracy(model, loader, pgd_fn, device))
        results["gaussian"].append(robust_accuracy(model, loader, gauss_fn, device))

    return results


def _pgd_craft(model, x, y, eps):
    return pgd_linf(
        model, x, y,
        eps=eps, steps=PGD_STEPS, step_size=eps / 4, random_start=PGD_RANDOM_START,
    )


def _transfer_craft(model, x, y, eps, opts: dict):
    """Surrogate-side crafting with transfer enhancements (MI/DI/TI/margin)."""
    return transfer_pgd_linf(
        model, x, y,
        eps=eps, steps=PGD_STEPS, step_size=eps / 4, random_start=PGD_RANDOM_START,
        momentum=opts["momentum"], di_prob=opts["di_prob"],
        ti_kernel_size=opts["ti_kernel"], ti_sigma=opts["ti_sigma"],
        loss=opts["loss"], image_size=IMAGE_SIZE,
    )


def _default_transfer_opts() -> dict:
    return {"loss": "ce", "momentum": 0.0, "di_prob": 0.0, "ti_kernel": 0, "ti_sigma": 0.0}


def evaluate_suite(
    surrogate,
    surrogate_name: str,
    target_models: dict,
    loader: DataLoader,
    device: torch.device,
    epsilons: list[float],
    *,
    whitebox: bool = False,
    transfer_opts: dict | None = None,
) -> dict[str, dict[str, list[float]]]:
    """
    Transfer (black-box) evaluation.

    Adversarial examples are crafted ONCE on the surrogate per batch, then transferred
    to each held-out target model (attack key ``pgd_transfer``). The Gaussian baseline
    (model-agnostic) is reported per model. With ``whitebox=True`` we also craft PGD on
    each model itself (``pgd_whitebox``) as an upper-bound reference, and include the
    surrogate as a reported model.
    """
    if transfer_opts is None:
        transfer_opts = _default_transfer_opts()

    report_models: dict = dict(target_models)
    if whitebox:
        report_models = {surrogate_name: surrogate, **target_models}

    results: dict[str, dict[str, list[float]]] = {}
    for name in report_models:
        results[name] = {"pgd_transfer": [], "gaussian": []} if name in target_models else {"gaussian": []}
        if whitebox:
            results[name]["pgd_whitebox"] = []

    for eps in epsilons:
        if eps <= 0:
            for name, m in report_models.items():
                acc = accuracy(m, loader, device)
                for key in results[name]:
                    results[name][key].append(acc)
            continue

        tgt_pgd_correct = {n: 0 for n in target_models}
        gauss_correct = {n: 0 for n in report_models}
        total = 0
        for images, labels in tqdm(loader, desc=f"transfer eps={eps:.4f}", leave=False):
            images = images.to(device)
            labels = labels.to(device)
            total += labels.size(0)

            x_adv = _transfer_craft(surrogate, images, labels, eps, transfer_opts)
            x_gauss = gaussian_linf_baseline(images, eps, variance=GAUSSIAN_VARIANCE)
            with torch.no_grad():
                for name, m in report_models.items():
                    gauss_correct[name] += (m(x_gauss).argmax(1) == labels).sum().item()
                for name, m in target_models.items():
                    tgt_pgd_correct[name] += (m(x_adv).argmax(1) == labels).sum().item()

        for name in report_models:
            results[name]["gaussian"].append(gauss_correct[name] / max(total, 1))
        for name in target_models:
            results[name]["pgd_transfer"].append(tgt_pgd_correct[name] / max(total, 1))

        if whitebox:
            for name, m in report_models.items():
                wb_fn = lambda mm, x, y, e=eps, mdl=m: _pgd_craft(mdl, x, y, e)
                results[name]["pgd_whitebox"].append(robust_accuracy(m, loader, wb_fn, device))

    return results


def save_results_csv(
    out_path: Path,
    epsilons: list[float],
    all_results: dict[str, dict[str, list[float]]],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "attack", "epsilon", "robust_accuracy"])
        for model_name, attacks in all_results.items():
            for attack_name, accs in attacks.items():
                for eps, acc in zip(epsilons, accs):
                    w.writerow([model_name, attack_name, eps, f"{acc:.6f}"])


def cmd_smoke(args: argparse.Namespace) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    subset = ImageNetSubset()
    loader = make_loader(subset, batch_size=args.batch_size, max_n=args.n or 10)

    model_names = [args.model or STANDARD_MODEL_NAME]
    if args.with_robust:
        model_names.append(ROBUST_MODEL_NAME)

    epsilons = [0.0, args.eps]
    for model_name in model_names:
        print(f"\nSmoke test: model={model_name}, n={args.n}, eps={epsilons}")
        results = evaluate_model(model_name, loader, device, epsilons)
        for attack, accs in results.items():
            print(f"  {attack}: {accs}")


def cmd_full(args: argparse.Namespace) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    n_samples = args.n if args.n is not None else DEFAULT_N_SAMPLES
    subset = ImageNetSubset()
    available = {row.image_id for row in load_indices()}
    on_disk = {p.stem for p in subset.image_dir.glob("*.JPEG")}
    missing = available - on_disk
    if missing:
        print(f"WARNING: {len(missing)} images missing from data/. Run datasets/download.py first.")

    loader = make_loader(subset, batch_size=args.batch_size, max_n=n_samples)
    epsilons = EPSILONS if args.epsilons is None else args.epsilons

    transfer_opts = {
        "loss": args.transfer_loss if args.transfer_loss is not None else TRANSFER_LOSS,
        "momentum": args.mi_momentum if args.mi_momentum is not None else MI_MOMENTUM,
        "di_prob": args.di_prob if args.di_prob is not None else DI_PROB,
        "ti_kernel": args.ti_kernel if args.ti_kernel is not None else TI_KERNEL_SIZE,
        "ti_sigma": TI_SIGMA,
    }

    print(f"\nSurrogate (attacker's model): {SURROGATE_MODEL_NAME}")
    print(f"Targets (held-out): {', '.join(TARGET_MODEL_NAMES)}")
    print(f"Mode: transfer{' + whitebox reference' if args.whitebox else ''}")
    print(
        f"Transfer enhancements: loss={transfer_opts['loss']}, "
        f"MI={transfer_opts['momentum']}, DI={transfer_opts['di_prob']}, "
        f"TI={transfer_opts['ti_kernel']} (sigma={transfer_opts['ti_sigma']})"
    )

    surrogate = load_robustbench_model(SURROGATE_MODEL_NAME, device=device)
    target_models = {
        name: load_robustbench_model(name, device=device) for name in TARGET_MODEL_NAMES
    }

    t0 = time.time()
    all_results = evaluate_suite(
        surrogate,
        SURROGATE_MODEL_NAME,
        target_models,
        loader,
        device,
        epsilons,
        whitebox=args.whitebox,
        transfer_opts=transfer_opts,
    )
    auc_table: dict[str, dict[str, float]] = {}
    for name, attacks in all_results.items():
        auc_table[name] = {atk: compute_auc(epsilons, accs) for atk, accs in attacks.items()}
        print(f"\n=== {name} ===")
        for atk, auc_val in auc_table[name].items():
            print(f"  AUC ({atk}): {auc_val:.6f}")

    elapsed = time.time() - t0
    manifest = {
        "epsilons": epsilons,
        "results": all_results,
        "auc": auc_table,
        "n_samples": n_samples,
        "surrogate": SURROGATE_MODEL_NAME,
        "targets": list(TARGET_MODEL_NAMES),
        "whitebox": args.whitebox,
        "transfer_opts": transfer_opts,
        "elapsed_sec": round(elapsed, 2),
    }

    exp_id = next_exp_id()

    hyperparams = snapshot_hyperparameters(
        n_samples=n_samples,
        epsilons=epsilons,
        batch_size=args.batch_size,
        whitebox=args.whitebox,
        transfer_opts=transfer_opts,
    )
    surrogate_whitebox = None
    if args.whitebox:
        surrogate_whitebox = all_results.get(SURROGATE_MODEL_NAME, {}).get("pgd_whitebox")

    with tempfile.TemporaryDirectory() as td:
        csv_path = Path(td) / "results.csv"
        png_path = Path(td) / "curves.png"
        panels_path = Path(td) / "curves_panels.png"
        save_results_csv(csv_path, epsilons, all_results)
        plot_security_curves(all_results, epsilons, png_path)
        plot_per_model_panels(
            all_results,
            epsilons,
            panels_path,
            surrogate_name=SURROGATE_MODEL_NAME,
            surrogate_whitebox=surrogate_whitebox,
        )
        saved = save_experiment(
            exp_id=exp_id,
            hyperparams=hyperparams,
            manifest=manifest,
            results_csv=csv_path,
            curves_png=png_path,
            elapsed_sec=elapsed,
            panels_png=panels_path,
        )

    print(f"\nSaved experiment data to {saved}")
    print("outputs/ is yours to curate manually (place submission SOTA results there).")
    print("Record-keeping (log.md / baseline) is intentionally manual — update it yourself.")


def main() -> None:
    parser = argparse.ArgumentParser(description="MLSec Individual evaluation pipeline")
    parser.add_argument("--list-models", action="store_true", help="List RobustBench ImageNet Linf models")
    parser.add_argument("--smoke", action="store_true", help="Quick smoke test on small subset")
    parser.add_argument("--full", action="store_true", help="Full security evaluation")
    parser.add_argument("--model", type=str, default=None, help="Model name for smoke test")
    parser.add_argument(
        "--with-robust",
        action="store_true",
        help="Smoke test both standard and robust models",
    )
    parser.add_argument("--n", type=int, default=None, help="Sample count (smoke default 10, full default 4000)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--eps", type=float, default=4 / 255, help="Epsilon for smoke test")
    parser.add_argument("--epsilons", type=float, nargs="*", default=None, help="Custom epsilon list for --full")
    parser.add_argument(
        "--whitebox",
        action="store_true",
        help="Also compute white-box PGD (craft on each model itself) as a reference; slower.",
    )
    parser.add_argument(
        "--transfer-loss", choices=["ce", "margin"], default=None,
        help="Surrogate-craft loss (default: config TRANSFER_LOSS)",
    )
    parser.add_argument("--mi-momentum", type=float, default=None, help="MI-FGSM momentum (0 disables)")
    parser.add_argument("--di-prob", type=float, default=None, help="DI input-diversity prob (0 disables)")
    parser.add_argument("--ti-kernel", type=int, default=None, help="TI gaussian kernel size (<=1 disables)")
    args = parser.parse_args()

    if args.list_models:
        cmd_list_models()
    elif args.smoke:
        cmd_smoke(args)
    elif args.full:
        cmd_full(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
