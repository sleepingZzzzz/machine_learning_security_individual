"""Central configuration for paths, models, and hyperparameters."""

from pathlib import Path

# ── Project paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "datasets" / "imagenet_kaggle"
IMAGE_DIR = DATA_ROOT / "data"
# Dev set: 4000 images, balanced (4 per class), used for iteration.
INDICES_CSV = DATA_ROOT / "indices_4000_seed42.csv"
# Submission set: balanced 1000 (1 per class), a subset of the dev set.
SUBMISSION_INDICES_CSV = DATA_ROOT / "indices_1000_seed42.csv"
CIFAR10_DIR = PROJECT_ROOT / "datasets" / "cifar10"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
RUNS_DIR = PROJECT_ROOT / "runs"
LOG_MD = PROJECT_ROOT / "log.md"

# ── Models (ImageNet Linf — names from RobustBench model zoo) ─────────────
# "Standard" is CIFAR-only; ImageNet non-robust model is Standard_R50.
STANDARD_MODEL_NAME = "Standard_R50"
# Same ResNet-50 backbone family as Standard_R50; good default for comparison.
ROBUST_MODEL_NAME = "Engstrom2019Robustness"

# ── Transfer (black-box) attack setup ─────────────────────────────────────
# Surrogate = the model the attacker actually has. We use a *robust* ResNet-50
# (Salman2020Do_R50): adversarial examples crafted on robust features tend to
# transfer better, and an attack that defeats robust targets should a fortiori
# defeat the (easier) non-robust target. Surrogate is held-out from all targets.
SURROGATE_MODEL_NAME = "Salman2020Do_R50"
# Held-out targets simulating unknown defender models; disjoint from surrogate,
# spread across robustness and architectures (satisfies the assignment's
# "include one non-robust + one robust evaluated model" requirement):
#   Standard_R50                    - non-robust ResNet-50 (RobustBench standard)
#   Engstrom2019Robustness          - robust ResNet-50
#   Singh2023Revisiting_ConvNeXt-T  - robust modern CNN
#   Singh2023Revisiting_ViT-S       - robust vision transformer
TARGET_MODEL_NAMES = [
    "Standard_R50",
    "Engstrom2019Robustness",
    "Singh2023Revisiting_ConvNeXt-T-ConvStem",
    "Singh2023Revisiting_ViT-S-ConvStem",
]

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

# ── Transfer enhancements (applied ONLY when crafting on the surrogate) ──────
# Boost cross-model transferability. White-box reference (pgd_whitebox) stays
# plain PGD. Literature-standard defaults; CLI flags override per-run.
#   TRANSFER_LOSS: "ce" | "margin" (CW logit-margin, decision-boundary oriented)
#   MI_MOMENTUM  : MI-FGSM momentum decay (0 disables)
#   DI_PROB      : DI input-diversity probability (0 disables)
#   TI_KERNEL_SIZE: TI gaussian-kernel size (<=1 disables)
TRANSFER_LOSS = "margin"
MI_MOMENTUM = 1.0
DI_PROB = 0.7
TI_KERNEL_SIZE = 5
TI_SIGMA = 3.0

# ── Gaussian baseline ──────────────────────────────────────────────────────
GAUSSIAN_VARIANCE = 0.001

# ── Epsilon schedule ───────────────────────────────────────────────────────
EPSILONS = [0, 1 / 255, 2 / 255, 4 / 255, 6 / 255, 8 / 255]

# ── Defaults ───────────────────────────────────────────────────────────────
DEFAULT_SEED = 42
DEFAULT_N_SAMPLES = 4000
DEFAULT_PER_CLASS = 4
DEFAULT_BATCH_SIZE = 16
