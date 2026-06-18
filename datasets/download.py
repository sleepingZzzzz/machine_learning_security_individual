import argparse
import csv
import json
import os
import random
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path


COMPETITION = "imagenet-object-localization-challenge"
VAL_JPEG_PREFIX = "ILSVRC/Data/CLS-LOC/val/"


@dataclass(frozen=True)
class Sample:
    image_id: str  # e.g. ILSVRC2012_val_00000001
    wnid: str  # e.g. n01440764
    class_idx: int  # 0..999


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _run(cmd: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=False,
    )
    return proc.returncode, proc.stdout


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def unzip_if_needed(zip_path: Path, out_dir: Path) -> None:
    if not zip_path.exists():
        return
    ensure_dir(out_dir)
    log(f"Extracting {zip_path.name} -> {out_dir}")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)


def read_synset_mapping(mapping_path: Path) -> dict[str, int]:
    """
    LOC_synset_mapping.txt format (1000 lines):
      n01440764 tench, Tinca tinca
      ...
    We map wnid -> class_idx where class_idx is 0..999 in file order.
    """
    if not mapping_path.exists():
        raise FileNotFoundError(
            f"Missing `{mapping_path}`. Create it by copying the Kaggle page content into a local file."
        )
    lines = mapping_path.read_text(encoding="utf-8").splitlines()
    lines = [ln.strip() for ln in lines if ln.strip()]
    if len(lines) < 1000:
        raise ValueError(
            f"`{mapping_path}` seems incomplete: expected 1000 non-empty lines, got {len(lines)}."
        )
    wnids: list[str] = []
    for ln in lines[:1000]:
        wnid = ln.split()[0].strip()
        if not wnid.startswith("n"):
            raise ValueError(f"Unexpected line in `{mapping_path}`: {ln[:80]}")
        wnids.append(wnid)
    return {wnid: i for i, wnid in enumerate(wnids)}


def read_loc_val_solution(loc_csv_path: Path) -> list[tuple[str, str]]:
    """
    LOC_val_solution.csv format:
      ImageId,PredictionString
      ILSVRC2012_val_00048981,n03995372 85 1 499 272
    We parse (ImageId, wnid) where wnid is the first token of PredictionString.
    """
    if not loc_csv_path.exists():
        raise FileNotFoundError(f"Missing `{loc_csv_path}`. Download LOC_val_solution.csv(.zip) first.")
    items: list[tuple[str, str]] = []
    with loc_csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_id = (row.get("ImageId") or "").strip()
            pred = (row.get("PredictionString") or "").strip()
            if not image_id or not pred:
                continue
            wnid = pred.split()[0].strip()
            items.append((image_id, wnid))
    if not items:
        raise ValueError(f"No rows parsed from `{loc_csv_path}`.")
    return items


def choose_samples(
    items: list[tuple[str, str]],
    wnid_to_class_idx: dict[str, int],
    *,
    n_samples: int,
    seed: int,
) -> list[Sample]:
    filtered: list[tuple[str, str]] = [(img, wnid) for img, wnid in items if wnid in wnid_to_class_idx]
    if len(filtered) < n_samples:
        raise ValueError(
            f"Not enough labeled val rows after filtering: need {n_samples}, got {len(filtered)}."
        )
    rnd = random.Random(seed)
    picked = rnd.sample(filtered, n_samples)
    return [Sample(image_id=img, wnid=wnid, class_idx=wnid_to_class_idx[wnid]) for img, wnid in picked]


def write_indices_csv(samples: list[Sample], out_csv: Path) -> None:
    ensure_dir(out_csv.parent)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image_id", "wnid", "class_idx"])
        for s in samples:
            w.writerow([s.image_id, s.wnid, s.class_idx])


def move_existing_val_jpegs(root: Path, data_dir: Path) -> int:
    """
    Move any ILSVRC2012_val_*.JPEG from root into data_dir, to keep a clean structure.
    """
    ensure_dir(data_dir)
    moved = 0
    for p in root.glob("ILSVRC2012_val_*.JPEG"):
        target = data_dir / p.name
        if target.exists():
            p.unlink()
            continue
        shutil.move(str(p), str(target))
        moved += 1
    return moved


def ensure_kaggle_cli() -> None:
    log("Checking Kaggle CLI availability...")
    code, out = _run(["kaggle", "-v"])
    if code != 0:
        raise RuntimeError(
            "Kaggle CLI not available. Install and authenticate first.\n"
            "Try: `pip install --upgrade kaggle` and ensure credentials are set.\n"
            f"Output:\n{out}"
        )


def download_one_jpeg(
    *,
    image_id: str,
    out_dir: Path,
    quiet: bool,
    progress_prefix: str | None = None,
) -> tuple[bool, str | None]:
    """
    Downloads a single JPEG via Kaggle competitions API into out_dir.
    Kaggle CLI usually produces `<image_id>.JPEG.zip`, which we then unzip and delete.
    Returns: (ok, error_message)
    """
    ensure_dir(out_dir)
    jpeg_name = f"{image_id}.JPEG"
    jpeg_path = out_dir / jpeg_name
    if jpeg_path.exists():
        return True, None

    remote_path = f"{VAL_JPEG_PREFIX}{jpeg_name}"
    if progress_prefix:
        log(f"{progress_prefix} Downloading {remote_path}")
    cmd = [
        "kaggle",
        "competitions",
        "download",
        "-c",
        COMPETITION,
        "-f",
        remote_path,
        "-p",
        str(out_dir),
    ]
    if quiet:
        cmd.append("-q")

    code, out = _run(cmd)

    # Even when Kaggle prints some noise to stderr, it may succeed.
    zip_path = out_dir / f"{jpeg_name}.zip"
    if zip_path.exists():
        try:
            if progress_prefix:
                log(f"{progress_prefix} Extracting {zip_path.name}")
            unzip_if_needed(zip_path, out_dir)
            zip_path.unlink(missing_ok=True)
        except Exception as e:
            return False, f"Downloaded zip but failed to extract {zip_path.name}: {e}"

    if jpeg_path.exists():
        if progress_prefix:
            log(f"{progress_prefix} OK: {jpeg_name}")
        return True, None

    msg = out.strip() or "Unknown kaggle error"
    if progress_prefix:
        log(f"{progress_prefix} FAIL: {jpeg_name} ({msg.splitlines()[-1] if msg else 'unknown'})")
    return False, msg


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a 1000-sample ImageNet val subset from Kaggle for MLSec project."
    )
    parser.add_argument(
        "--root",
        type=str,
        default=str(Path(__file__).resolve().parent / "imagenet_kaggle"),
        help="Root directory of imagenet_kaggle (default: datasets/imagenet_kaggle).",
    )
    parser.add_argument("--n-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--max-download",
        type=int,
        default=0,
        help="If >0, only download up to this many images (useful for smoke tests).",
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce Kaggle CLI output.")
    parser.add_argument(
        "--log-every",
        type=int,
        default=1,
        help="Print per-image progress every N images (default: 1).",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    loc_csv = root / "LOC_val_solution.csv"
    loc_zip = root / "LOC_val_solution.csv.zip"
    mapping_path = root / "LOC_synset_mapping.txt"
    data_dir = root / "data"

    t0 = time.time()
    ensure_dir(root)
    ensure_dir(data_dir)

    ensure_kaggle_cli()

    # 1) Ensure LOC_val_solution.csv is present
    log("Step 1/5: Ensuring LOC_val_solution.csv is present...")
    if not loc_csv.exists() and loc_zip.exists():
        unzip_if_needed(loc_zip, root)
    if not loc_csv.exists():
        raise FileNotFoundError(
            f"`{loc_csv}` not found. You should have it already. If not, download it with:\n"
            f"  kaggle competitions download -c {COMPETITION} -f LOC_val_solution.csv -p {root}"
        )

    # 2) Ensure mapping exists (user-created)
    log("Step 2/5: Loading LOC_synset_mapping.txt (wnid -> class_idx)...")
    wnid_to_idx = read_synset_mapping(mapping_path)

    # 3) Normalize folder layout
    log("Step 3/5: Normalizing folder layout (moving existing val JPEGs into data/)...")
    moved = move_existing_val_jpegs(root, data_dir)
    if moved:
        log(f"Moved {moved} existing JPEG(s) into {data_dir}")

    # 4) Sample indices
    log("Step 4/5: Sampling indices and writing index CSV...")
    items = read_loc_val_solution(loc_csv)
    samples = choose_samples(items, wnid_to_idx, n_samples=args.n_samples, seed=args.seed)

    indices_csv = root / f"indices_{args.n_samples}_seed{args.seed}.csv"
    write_indices_csv(samples, indices_csv)
    log(f"Wrote indices CSV: {indices_csv}")

    # 5) Download images
    log("Step 5/5: Downloading images...")
    to_get = samples
    if args.max_download and args.max_download > 0:
        to_get = samples[: args.max_download]
        log(f"Smoke mode: only downloading first {len(to_get)} images (from sampled list).")

    failures: list[dict[str, str]] = []
    ok = 0
    skipped = 0

    for i, s in enumerate(to_get, start=1):
        jpeg_path = data_dir / f"{s.image_id}.JPEG"
        if jpeg_path.exists():
            skipped += 1
            if (i % max(1, args.log_every)) == 0:
                log(f"[{i}/{len(to_get)}] SKIP exists: {jpeg_path.name}")
            continue

        prefix = None
        if (i % max(1, args.log_every)) == 0:
            prefix = f"[{i}/{len(to_get)}]"
        success, err = download_one_jpeg(
            image_id=s.image_id,
            out_dir=data_dir,
            quiet=args.quiet,
            progress_prefix=prefix,
        )
        if success:
            ok += 1
        else:
            failures.append({"image_id": s.image_id, "wnid": s.wnid, "error": err or ""})

        if (i % 25) == 0:
            elapsed = time.time() - t0
            rate = (ok + skipped) / max(1.0, elapsed)
            log(f"Progress: [{i}/{len(to_get)}] ok={ok} skipped={skipped} fail={len(failures)} ({rate:.2f} img/s)")

    manifest = {
        "root": str(root),
        "n_samples": args.n_samples,
        "seed": args.seed,
        "max_download": args.max_download,
        "moved_existing_jpegs": moved,
        "downloaded": ok,
        "skipped_existing": skipped,
        "failed": failures,
        "indices_csv": str(indices_csv),
        "data_dir": str(data_dir),
        "elapsed_sec": round(time.time() - t0, 2),
    }
    (root / "download_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log("Done.")
    log(f"- indices: {indices_csv}")
    log(f"- images:  {data_dir}  (downloaded {ok}, skipped {skipped}, failed {len(failures)})")
    if failures:
        log("Some downloads failed. Re-run the script to retry; it will skip existing JPEGs.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
