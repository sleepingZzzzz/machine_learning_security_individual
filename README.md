# MLSec Individual Project

Adversarial robustness evaluation on ImageNet under the L∞ threat model. Attacks are
crafted on a **surrogate** (`Standard_R50`) and **transferred** to held-out target models
(black-box setting), compared against a random Gaussian baseline via security evaluation
curves and AUC. A balanced 4000-image dev set is used for iteration; a balanced 1000-image
subset is used for submission.

## Setup

See `requirements.txt` for dependencies (conda env `mlsec`).

```powershell
conda activate mlsec
pip install -r requirements.txt
```

## Data

```powershell
# Balanced ImageNet val (4/class = 4000 dev + 1/class = 1000 submission) + CIFAR-10
python datasets/download.py --per-class 4 --seed 42 --quiet
```

This writes `indices_4000_seed42.csv` (dev) and `indices_1000_seed42.csv` (submission),
keeps only the canonical balanced JPEGs in `datasets/imagenet_kaggle/data/`, and downloads
the CIFAR-10 test set into `datasets/cifar10/` (use `--skip-cifar10` to skip).

## Run

```powershell
# List available RobustBench models
python -m src.run --list-models

# Smoke test (10 images, standard model)
python -m src.run --smoke --n 10

# Full transfer evaluation (craft on surrogate, evaluate held-out targets)
python -m src.run --full

# Add white-box reference curves (craft on each model itself; slower)
python -m src.run --full --whitebox
```

Record-keeping is manual by design: `--full` only archives experiment *data*
(`config.json`, `results.csv`, `curves.png`, `run_manifest.json`) into a fresh
`runs/expN/`. Writing `log.md` and judging baselines is done by hand to force
deeper reflection on each iteration.

## Project Structure

```
src/
  config.py              # paths, hyperparameters, tentative model names
  data/                  # dataset loading & transforms
  models/                # RobustBench loader
  attacks/               # PGD-Linf & Gaussian baseline
  eval/                  # metrics, AUC, plotting
  run.py                 # entry point
datasets/
  download.py            # balanced ImageNet subset + CIFAR-10 downloader
  imagenet_kaggle/       # images + indices CSV (gitignored)
  cifar10/               # CIFAR-10 test set (gitignored)
runs/                    # full experiment data snapshots (exp1, exp2, ...)
log.md                   # experiment log (manual, full runs only)
outputs/                 # manually curated submission/SOTA results (tracked)
```
