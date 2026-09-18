# MLSec Individual Project — L∞ Adversarial Evasion Evaluation

Security evaluation of ImageNet classifiers against **L∞ adversarial evasion** attacks,
benchmarked against a random **Gaussian-noise baseline** via **security evaluation curves**
and their **AUC**.

The attack is **black-box / transfer**: adversarial examples are crafted on a **surrogate**
the attacker owns, then transferred to **held-out target models** (the attacker never sees
the targets' gradients). Per the assignment, the evaluated targets include **one non-robust
model** (`Standard_R50`) and **robust models** (RobustBench). The strongest configuration
uses a **robust multi-architecture ensemble surrogate** (a robust CNN + a robust Transformer).
The same recipe is additionally re-run on **CIFAR-10** (its own RobustBench model family) to
confirm the attack's **cross-dataset generalization**.

- **Threat model:** L∞, ε ∈ {0, 1/255, 2/255, 4/255, 6/255, 8/255}
- **Attack:** PGD-L∞ (20 steps, step = ε/4, random start), optional transfer enhancements (MI / DI / TI / CW-margin)
- **Baseline:** Gaussian noise centered at ε, variance 0.001, projected to the same L∞ ball
- **Metric:** robust accuracy vs ε curve, and trapezoidal AUC (lower = stronger attack)
- **Data:** balanced ImageNet-val subset — 4000 images (4/class) for iteration, 1000 (1/class) for submission; plus a balanced CIFAR-10 subset (100/class) for a cross-dataset generalization check

## 1. Setup

```powershell
conda activate mlsec
pip install -r requirements.txt
```

## 2. Prepare data

```powershell
# Balanced ImageNet val (4/class = 4000 dev + 1/class = 1000 submission) + CIFAR-10
python datasets/download.py --per-class 4 --seed 42 --quiet
```

Writes `indices_4000_seed42.csv` (dev) and `indices_1000_seed42.csv` (submission), keeps the
balanced JPEGs in `datasets/imagenet_kaggle/data/`, and downloads CIFAR-10 test into
`datasets/cifar10/` (use `--skip-cifar10` to skip).

## 3. Run

```powershell
# List available RobustBench ImageNet/L∞ models
python -m src.run --list-models

# Smoke test (10 images)
python -m src.run --smoke --n 10

# BEST / default: robust multi-architecture ensemble surrogate (CNN + Transformer) + MI.
# The config defaults already reproduce the submitted SOTA (baseline3 / exp9), 4000-img dev set.
python -m src.run --full --batch-size 32

# Same recipe on the balanced 1000 ImageNet submission set (aligns with the assignment's "1000 samples")
python -m src.run --full --submission --batch-size 32

# Cross-dataset generalization check: same transfer recipe on a balanced CIFAR-10 subset
python -m src.run --full --dataset cifar10

# Optional white-box reference curves (craft on each target itself; slower)
python -m src.run --full --whitebox

# (To use a single robust surrogate instead of the ensemble, set SURROGATE_MODE="single" in src/config.py.)
```

Each `--full` archives experiment **data** into a fresh `runs/expN/`
(`config.json`, `results.csv`, `curves.png`, `curves_panels.png`, `run_manifest.json`,
`meta.json`). The experiment log (`log.md`) and baseline judgements are maintained **by hand**.

Key CLI flags: `--dataset {imagenet,cifar10}`, `--submission` (ImageNet 1000 set),
`--batch-size`, `--n`, `--epsilons`, `--transfer-loss {ce,margin}`, `--mi-momentum`,
`--di-prob`, `--ti-kernel`, `--surrogate-ensemble`, `--whitebox`.

## 4. Program files — purpose of each

| File | Purpose |
|---|---|
| `src/run.py` | Main entry point / CLI (`--dataset {imagenet,cifar10}`, `--submission`, …). Builds the surrogate (single or ensemble) and target models per dataset profile, runs transfer (and optional white-box) evaluation, computes AUC, plots curves, snapshots results to `runs/expN/`. |
| `src/config.py` | Central configuration: paths, dataset/threat model, per-dataset model profiles (surrogate/targets for ImageNet & CIFAR-10 via `get_dataset_profile`), ε schedule, PGD & Gaussian hyperparameters, transfer-enhancement and ensemble settings. |
| `src/data/imagenet_subset.py` | Loads the fixed balanced ImageNet-val subset from the indices CSV (image id → class label). |
| `src/data/cifar_subset.py` | Deterministic balanced CIFAR-10 test subset (100/class) in [0,1], for the cross-dataset generalization check. |
| `src/data/transforms.py` | ImageNet eval preprocessing (Resize → CenterCrop → ToTensor to [0,1]) and the ImageNet normalization transform. |
| `src/models/robustbench_loader.py` | Loads RobustBench models (ImageNet **or** CIFAR-10, L∞; they embed input normalization) and lists the model zoo. |
| `src/models/normalized_model.py` | Utility wrapper to run attacks in [0,1] pixel space while the model sees normalized input. Not wired into the current pipeline (RobustBench models normalize internally); kept as a reusable helper. |
| `src/models/ensemble.py` | Probability-averaged **ensemble surrogate** (scale-balanced across heterogeneous members); returns log of mean probabilities so CE/margin behave correctly, gradients flow to all members. |
| `src/attacks/pgd_linf.py` | Plain PGD-L∞ attack (sign-gradient ascent, L∞-ball + [0,1] projection, random start). |
| `src/attacks/transfer_pgd.py` | Transfer-oriented PGD-L∞: MI (momentum), DI (input diversity), TI (Gaussian-kernel gradient smoothing), and CW-margin loss; degrades to plain PGD when disabled. |
| `src/attacks/gaussian_linf.py` | Random Gaussian-noise baseline (mean ε, variance 0.001), projected to the L∞ ball. |
| `src/eval/robust_accuracy.py` | Clean accuracy and robust accuracy (accuracy under an attack) over a data loader. |
| `src/eval/auc.py` | Trapezoidal Area Under the Security Evaluation Curve. |
| `src/eval/sec_curve.py` | Plots security curves: one combined overview and a per-model panel grid (with optional surrogate white-box reference). |
| `src/eval/exp_manager.py` | Snapshots each run's hyperparameters, manifest, results CSV, and figures into `runs/expN/`. |
| `src/{,data/,models/,attacks/,eval/}__init__.py` | Package markers. |
| `datasets/download.py` | Builds the balanced ImageNet-val subset (offline from a local val pack) and downloads CIFAR-10. |
| `requirements.txt` | Python dependencies (conda env `mlsec`). |

## 5. Files to include in `XX-YY-Program.zip`

Include (source + docs + evidence; everything needed to reproduce):

```
README.md
requirements.txt
src/                # all .py files (config, run, data/, models/, attacks/, eval/)
datasets/download.py
log.md              # experiment log: iteration history + baseline judgements
outputs/            # curated result snapshots backing the report (see layout below)
```

`outputs/` holds the three result sets the report relies on (each = the corresponding
`runs/expN/` content: `results.csv`, `curves.png`, `curves_panels.png`, `run_manifest.json`,
`config.json`, `meta.json`):

```
outputs/ImageNet-4000/   # exp9  = baseline3 (ImageNet, 4000 dev) — headline SOTA
outputs/ImageNet-1000/   # exp10 = baseline3 recipe on the 1000 submission set
outputs/CIFAR10-1000/    # exp11 = same recipe on CIFAR-10 (cross-dataset check)
```

Do **not** include (large / regenerable / private):

```
datasets/imagenet_kaggle/, datasets/cifar10/, datasets/imagenet_full/   # data, regenerable
models/                                                                  # model-weight cache
runs/                                                                    # raw per-run snapshots (curated copies live in outputs/)
.log/                                                                    # private notes
Project-ind.pdf, report-ind.docx                                         # spec / report source
__pycache__/, *.pyc
```

> The report goes in the final `XX-YY.zip` as a **separate** `XX-YY-Report.pdf`, not inside `XX-YY-Program.zip`.
> Final submission: `XX-YY.zip` = { `XX-YY-Program.zip`, `XX-YY-Report.pdf` }.
