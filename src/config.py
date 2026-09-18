"""Central configuration for paths, models, and hyperparameters."""

from dataclasses import dataclass
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
# Surrogate mode: "single" uses SURROGATE_MODEL_NAME; "ensemble" uses
# SURROGATE_ENSEMBLE (probability-averaged). Multi-architecture *robust* ensemble
# keeps gradient quality high (non-robust members proven unhelpful, see log.md).
# Default = "ensemble": this is the submitted SOTA (baseline3 / exp9), so a bare
# `python -m src.run --full` reproduces outputs/.
SURROGATE_MODE = "ensemble"
SURROGATE_ENSEMBLE = [
    "Salman2020Do_R50",              # robust CNN (ResNet-50)
    "Debenedetti2022Light_XCiT-S12",  # robust transformer (XCiT), orthogonal arch
]
SURROGATE_ENSEMBLE_WEIGHTS = None  # None = equal weights
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
# DI/TI default to OFF: ablations (exp4/exp7/exp8) showed both *hurt* transfer
# from a robust surrogate (esp. TI low-pass damaging high-frequency attacks on
# non-robust targets). Re-enable via CLI only for deliberate experiments.
# Default loss = "ce": matches the submitted SOTA (baseline3 / exp9); margin was
# ablated as neutral (exp5/exp6). Override per-run with --transfer-loss.
TRANSFER_LOSS = "ce"
MI_MOMENTUM = 1.0
DI_PROB = 0.0
TI_KERNEL_SIZE = 0
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

# ── CIFAR-10 (supplementary: cross-dataset generalization check) ────────────
# Same transfer recipe as ImageNet (held-out targets, robust ensemble surrogate),
# on a *different* dataset to test whether the attack generalizes. RobustBench
# CIFAR-10/Linf models take [0,1] 32x32 input (normalization is internal). All
# surrogate members are disjoint from the targets.
CIFAR10_IMAGE_SIZE = 32
CIFAR10_PER_CLASS = 100  # balanced 100/class = 1000 (mirrors the ImageNet 1000 set)
CIFAR10_SURROGATE_MODEL_NAME = "Carmon2019Unlabeled"        # robust WRN-28-10
CIFAR10_SURROGATE_MODE = "ensemble"
CIFAR10_SURROGATE_ENSEMBLE = [
    "Carmon2019Unlabeled",              # robust WRN-28-10
    "Andriushchenko2020Understanding",  # robust PreActResNet-18 (different arch)
]
CIFAR10_SURROGATE_ENSEMBLE_WEIGHTS = None  # None = equal weights
CIFAR10_TARGET_MODEL_NAMES = [
    "Standard",                 # non-robust (RobustBench CIFAR-10 standard)
    "Engstrom2019Robustness",   # robust ResNet-50
    "Wong2020Fast",             # robust PreActResNet-18
    "Rice2020Overfitting",      # robust WRN-34-20
]


@dataclass(frozen=True)
class DatasetProfile:
    """Everything the pipeline needs to run on one dataset."""

    name: str                 # "imagenet" | "cifar10"
    rb_dataset: str           # RobustBench dataset enum value
    data_kind: str            # how to build the data loader ("imagenet"|"cifar10")
    image_size: int
    surrogate_mode: str       # "single" | "ensemble"
    surrogate_single: str
    surrogate_ensemble: list[str]
    surrogate_ensemble_weights: list[float] | None
    targets: list[str]


def get_dataset_profile(name: str) -> DatasetProfile:
    if name == "imagenet":
        return DatasetProfile(
            name="imagenet",
            rb_dataset="imagenet",
            data_kind="imagenet",
            image_size=IMAGE_SIZE,
            surrogate_mode=SURROGATE_MODE,
            surrogate_single=SURROGATE_MODEL_NAME,
            surrogate_ensemble=list(SURROGATE_ENSEMBLE),
            surrogate_ensemble_weights=SURROGATE_ENSEMBLE_WEIGHTS,
            targets=list(TARGET_MODEL_NAMES),
        )
    if name == "cifar10":
        return DatasetProfile(
            name="cifar10",
            rb_dataset="cifar10",
            data_kind="cifar10",
            image_size=CIFAR10_IMAGE_SIZE,
            surrogate_mode=CIFAR10_SURROGATE_MODE,
            surrogate_single=CIFAR10_SURROGATE_MODEL_NAME,
            surrogate_ensemble=list(CIFAR10_SURROGATE_ENSEMBLE),
            surrogate_ensemble_weights=CIFAR10_SURROGATE_ENSEMBLE_WEIGHTS,
            targets=list(CIFAR10_TARGET_MODEL_NAMES),
        )
    raise ValueError(f"Unknown dataset: {name!r} (expected 'imagenet' or 'cifar10')")
