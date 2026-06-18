"""Experiment data snapshots under runs/expN.

Note: log.md / baseline record-keeping is intentionally NOT automated here —
the user maintains those manually to encourage deeper reflection. This module
only archives experiment *data* (config snapshot, results, curves, manifest).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src import config as cfg


def runs_dir() -> Path:
    return cfg.RUNS_DIR


def next_exp_id() -> int:
    root = runs_dir()
    root.mkdir(parents=True, exist_ok=True)
    max_id = 0
    for p in root.iterdir():
        if p.is_dir():
            m = re.fullmatch(r"exp(\d+)", p.name)
            if m:
                max_id = max(max_id, int(m.group(1)))
    return max_id + 1


def exp_dir(exp_id: int) -> Path:
    return runs_dir() / f"exp{exp_id}"


def snapshot_hyperparameters(
    *,
    n_samples: int,
    epsilons: list[float],
    batch_size: int,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "standard_model": cfg.STANDARD_MODEL_NAME,
        "robust_model": cfg.ROBUST_MODEL_NAME,
        "dataset": cfg.DATASET,
        "threat_model": cfg.THREAT_MODEL,
        "n_samples": n_samples,
        "epsilons": epsilons,
        "batch_size": batch_size,
        "pgd_steps": cfg.PGD_STEPS,
        "pgd_random_start": cfg.PGD_RANDOM_START,
        "gaussian_variance": cfg.GAUSSIAN_VARIANCE,
        "resize_size": cfg.RESIZE_SIZE,
        "image_size": cfg.IMAGE_SIZE,
        "indices_csv": str(cfg.INDICES_CSV),
    }


def save_experiment(
    *,
    exp_id: int,
    hyperparams: dict[str, Any],
    manifest: dict[str, Any],
    results_csv: Path,
    curves_png: Path,
    elapsed_sec: float,
) -> Path:
    out = exp_dir(exp_id)
    out.mkdir(parents=True, exist_ok=True)

    (out / "config.json").write_text(json.dumps(hyperparams, indent=2), encoding="utf-8")
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    meta = {
        "exp_id": exp_id,
        "elapsed_sec": round(elapsed_sec, 2),
        "paths": {
            "results_csv": "results.csv",
            "curves_png": "curves.png",
            "config": "config.json",
            "manifest": "run_manifest.json",
        },
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    shutil.copy2(results_csv, out / "results.csv")
    shutil.copy2(curves_png, out / "curves.png")
    return out
