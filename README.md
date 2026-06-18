# MLSec Individual Project

Adversarial robustness evaluation on ImageNet (1000-sample subset) under L∞ threat model.

## Setup

See `requirements.txt` for dependencies (conda env `mlsec`).

```powershell
conda activate mlsec
pip install -r requirements.txt
```

## Data

```powershell
python datasets/download.py --n-samples 1000 --seed 42 --quiet
```

## Run

```powershell
# List available RobustBench models
python -m src.run --list-models

# Smoke test (10 images, standard model)
python -m src.run --smoke --n 10

# Smoke test both standard + robust
python -m src.run --smoke --with-robust --n 10

# Full evaluation (1000 images; archives data to runs/expN + outputs/)
python -m src.run --full
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
  download.py            # ImageNet 1000-sample downloader
  imagenet_kaggle/       # images + indices CSV
runs/                    # full experiment data snapshots (exp1, exp2, ...)
log.md                   # experiment log (manual, full runs only)
outputs/                 # latest full run mirror
```
