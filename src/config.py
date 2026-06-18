"""Central configuration for paths, models, and hyperparameters."""

from pathlib import Path

# ── Project paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "datasets" / "imagenet_kaggle"
IMAGE_DIR = DATA_ROOT / "data"
INDICES_CSV = DATA_ROOT / "indices_1000_seed42.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
RUNS_DIR = PROJECT_ROOT / "runs"
LOG_MD = PROJECT_ROOT / "log.md"

# ── Models (ImageNet Linf — names from RobustBench model zoo) ─────────────
# "Standard" is CIFAR-only; ImageNet non-robust model is Standard_R50.
STANDARD_MODEL_NAME = "Standard_R50"
# Same ResNet-50 backbone family as Standard_R50; good default for comparison.
ROBUST_MODEL_NAME = "Engstrom2019Robustness"

# Other reasonable robust candidates (see --list-models):
#   Salman2020Do_R50, Salman2020Do_50_2, Wong2020Fast
RECOMMENDED_ROBUST_MODELS = [
    "Engstrom2019Robustness",
    "Salman2020Do_R50",
    "Salman2020Do_50_2",
]

DATASET = "imagenet"
THREAT_MODEL = "Linf"

# ── Preprocessing ──────────────────────────────────────────────────────────
# RobustBench ImageNet models embed Normalize(mean, std) internally.
# Our pipeline feeds [0, 1] tensors after Resize/CenterCrop/ToTensor.
IMAGE_SIZE = 224
RESIZE_SIZE = 256
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

# ── PGD-L∞ ─────────────────────────────────────────────────────────────────
PGD_STEPS = 20
PGD_RANDOM_START = True

# ── Gaussian baseline ──────────────────────────────────────────────────────
GAUSSIAN_VARIANCE = 0.001

# ── Epsilon schedule ───────────────────────────────────────────────────────
EPSILONS = [0, 1 / 255, 2 / 255, 4 / 255, 6 / 255, 8 / 255]

# ── Defaults ───────────────────────────────────────────────────────────────
DEFAULT_SEED = 42
DEFAULT_N_SAMPLES = 1000
DEFAULT_BATCH_SIZE = 16
