"""Load the fixed 1000-sample ImageNet val subset."""

import csv
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from torch.utils.data import Dataset

from src.config import IMAGE_DIR, INDICES_CSV


@dataclass(frozen=True)
class IndexRow:
    image_id: str
    wnid: str
    class_idx: int


def load_indices(csv_path: Path | None = None) -> list[IndexRow]:
    csv_path = csv_path or INDICES_CSV
    rows: list[IndexRow] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                IndexRow(
                    image_id=row["image_id"].strip(),
                    wnid=row["wnid"].strip(),
                    class_idx=int(row["class_idx"]),
                )
            )
    if not rows:
        raise ValueError(f"No rows in {csv_path}")
    return rows


class ImageNetSubset(Dataset):
    """PIL image + class_idx from indices CSV."""

    def __init__(self, image_dir: Path | None = None, indices: list[IndexRow] | None = None):
        self.image_dir = image_dir or IMAGE_DIR
        self.indices = indices if indices is not None else load_indices()

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, idx: int) -> tuple[Image.Image, int]:
        row = self.indices[idx]
        path = self.image_dir / f"{row.image_id}.JPEG"
        if not path.exists():
            raise FileNotFoundError(f"Missing image: {path}")
        img = Image.open(path).convert("RGB")
        return img, row.class_idx
