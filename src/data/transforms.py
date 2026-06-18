"""ImageNet preprocessing transforms."""

from torchvision import transforms

from src.config import IMAGENET_MEAN, IMAGENET_STD, IMAGE_SIZE, RESIZE_SIZE


def get_eval_transform():
    """Standard ImageNet eval pipeline (no tensor augmentation)."""
    return transforms.Compose(
        [
            transforms.Resize(RESIZE_SIZE),
            transforms.CenterCrop(IMAGE_SIZE),
            transforms.ToTensor(),
        ]
    )


def get_normalize_transform():
    """Normalization applied after attack perturbation."""
    return transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)


def get_full_transform():
    """Resize + crop + to tensor + normalize (for clean inference only)."""
    return transforms.Compose([get_eval_transform(), get_normalize_transform()])
