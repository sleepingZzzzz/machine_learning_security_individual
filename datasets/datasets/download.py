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


def choose_samples_stratified(
    items: list[tuple[str, str]],
    wnid_to_class_idx: dict[str, int],
    *,
    per_class: int,
    seed: int,
) -> list[Sample]:
    """
    Balanced (stratified) sampling: pick exactly `per_class` images for EACH of the
    1000 classes. Deterministic given `seed` and class order, so the canonical set
    is reproducible and resumable.
    """
    by_wnid: dict[str, list[str]] = {}
    for img, wnid in items:
        if wnid in wnid_to_class_idx:
            by_wnid.setdefault(wnid, []).append(img)

    rnd = random.Random(seed)
    samples: list[Sample] = []
    for wnid in sorted(wnid_to_class_idx, key=lambda w: wnid_to_class_idx[w]):
        pool = sorted(by_wnid.get(wnid, []))
        if len(pool) < per_class:
            raise ValueError(
                f"Class {wnid} has only {len(pool)} val image(s), need {per_class}."
            )
        picked = sorted(rnd.sample(pool, per_class))
        for img in picked:
            samples.append(Sample(image_id=img, wnid=wnid, class_idx=wnid_to_class_idx[wnid]))
    return samples


def take_per_class(samples: list[Sample], k: int) -> list[Sample]:
    """Return a balanced subset with the first `k` samples of each class."""
    seen: dict[int, int] = {}
    out: list[Sample] = []
    for s in samples:
        c = seen.get(s.class_idx, 0)
        if c < k:
            out.append(s)
            seen[s.class_idx] = c + 1
    return out


def round_robin_order(samples: list[Sample]) -> list[Sample]:
    """
    Reorder class-contiguous samples into round-robin: all 1st-per-class first,
    then all 2nd-per-class, ... So an interrupted download still yields a subset
    that covers every class (and the balanced 1/class set completes first).
    """
    by_class: dict[int, list[Sample]] = {}
    for s in samples:
        by_class.setdefault(s.class_idx, []).append(s)

    out: list[Sample] = []
    rank = 0
    while True:
        added = False
        for cls in sorted(by_class):
            if rank < len(by_class[cls]):
                out.append(by_class[cls][rank])
                added = True
        if not added:
            break
        rank += 1
    return out


def cleanup_data_dir(data_dir: Path, canonical_ids: set[str]) -> int:
    """Delete any *.JPEG in data_dir whose id is not in the canonical set."""
    removed = 0
    for p in data_dir.glob("*.JPEG"):
        if p.stem not in canonical_ids:
            p.unlink(missing_ok=True)
            removed += 1
    return removed


def download_cifar10(out_dir: Path) -> None:
    """Download the CIFAR-10 test set (separate label space, used for supplementary cross-dataset attacks)."""
    ensure_dir(out_dir)
    try:
        from torchvision.datasets import CIFAR10
    except ImportError as e:
        raise RuntimeError(
            "torchvision is required to download CIFAR-10. Install it (see requirements.txt)."
        ) from e
    log(f"Downloading CIFAR-10 test set -> {out_dir}")
    CIFAR10(root=str(out_dir), train=False, download=True)
    log("CIFAR-10 ready.")


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
    max_retries: int = 5,
    backoff_base: float = 5.0,
) -> tuple[bool, str | None]:
    """
    Downloads a single JPEG via Kaggle competitions API into out_dir.
    Kaggle CLI usually produces `<image_id>.JPEG.zip`, which we then unzip and delete.
    On HTTP 429 (rate limit) it retries with exponential backoff.
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

    zip_path = out_dir / f"{jpeg_name}.zip"
    last_msg: str | None = None
    for attempt in range(max_retries + 1):
        code, out = _run(cmd)

        # Even when Kaggle prints some noise to stderr, it may succeed.
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

        last_msg = out.strip() or "Unknown kaggle error"
        rate_limited = ("429" in last_msg) or ("Too Many Requests" in last_msg)
        if rate_limited and attempt < max_retries:
            wait = backoff_base * (2 ** attempt)
            log(
                f"{progress_prefix or ''} 429 rate-limited; backing off {wait:.0f}s "
                f"(retry {attempt + 1}/{max_retries})"
            )
            time.sleep(wait)
            continue
        break

    if progress_prefix:
        tail = last_msg.splitlines()[-1] if last_msg else "unknown"
        log(f"{progress_prefix} FAIL: {jpeg_name} ({tail})")
    return False, last_msg


def populate_from_local_val(
    samples: list[Sample],
    local_val_dir: Path,
    data_dir: Path,
    *,
    log_every: int = 50,
) -> tuple[int, int, list[dict[str, str]]]:
    """
    Copy the sampled JPEGs from a locally extracted ImageNet val directory
    (layout: <local_val_dir>/<wnid>/<image_id>.JPEG) into data_dir as flat
    <image_id>.JPEG files. Skips files already present. This is the offline
    alternative to per-file Kaggle downloads (no rate limit).
    Returns: (copied, skipped, failures)
    """
    ensure_dir(data_dir)
    copied = 0
    skipped = 0
    failures: list[dict[str, str]] = []
    n = len(samples)
    for i, s in enumerate(samples, start=1):
        dst = data_dir / f"{s.image_id}.JPEG"
        if dst.exists():
            skipped += 1
            if (i % max(1, log_every)) == 0:
                log(f"[{i}/{n}] SKIP exists: {dst.name}")
            continue

        src = local_val_dir / s.wnid / f"{s.image_id}.JPEG"
        if not src.exists():
            # Fallback: filenames are globally unique, search recursively.
            matches = list(local_val_dir.rglob(f"{s.image_id}.JPEG"))
            src = matches[0] if matches else src
        if not src.exists():
            failures.append(
                {"image_id": s.image_id, "wnid": s.wnid, "error": "not found in local val dir"}
            )
            log(f"[{i}/{n}] FAIL not found: {s.image_id}.JPEG")
            continue

        try:
            shutil.copy2(str(src), str(dst))
            copied += 1
            if (i % max(1, log_every)) == 0:
                log(f"[{i}/{n}] copied {dst.name}")
        except Exception as e:  # noqa: BLE001
            failures.append({"image_id": s.image_id, "wnid": s.wnid, "error": str(e)})
            log(f"[{i}/{n}] FAIL copy: {s.image_id}.JPEG ({e})")
    return copied, skipped, failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a balanced ImageNet val subset (default 4/class = 4000) from Kaggle, plus CIFAR-10."
    )
    parser.add_argument(
        "--root",
        type=str,
        default=str(Path(__file__).resolve().parent / "imagenet_kaggle"),
        help="Root directory of imagenet_kaggle (default: datasets/imagenet_kaggle).",
    )
    parser.add_argument(
        "--from-local-val",
        type=str,
        default="",
        help=(
            "Path to a locally extracted ImageNet val dir "
            "(layout <dir>/<wnid>/<image_id>.JPEG). If set, the sampled JPEGs are "
            "copied from here instead of being downloaded from Kaggle (no rate limit)."
        ),
    )
    parser.add_argument(
        "--per-class",
        type=int,
        default=4,
        help="Images per class for the balanced dev set (default 4 -> 4000 total).",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--max-download",
        type=int,
        default=0,
        help="If >0, only download up to this many images (useful for smoke tests).",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not delete JPEGs that are outside the canonical balanced set.",
    )
    parser.add_argument(
        "--skip-cifar10",
        action="store_true",
        help="Skip downloading the CIFAR-10 test set.",
    )
    parser.add_argument(
        "--cifar10-dir",
        type=str,
        default=str(Path(__file__).resolve().parent / "cifar10"),
        help="Directory for the CIFAR-10 test set (default: datasets/cifar10).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Throttle: seconds to sleep between image downloads (default 0.5).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Retries on HTTP 429 (rate limit) per image, with exponential backoff.",
    )
    parser.add_argument(
        "--backoff",
        type=float,
        default=5.0,
        help="Base seconds for exponential backoff on 429 (5 -> 5,10,20,...).",
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
    local_val = Path(args.from_local_val).resolve() if args.from_local_val else None

    t0 = time.time()
    ensure_dir(root)
    ensure_dir(data_dir)

    if local_val is None:
        ensure_kaggle_cli()
    else:
        if not local_val.exists():
            raise FileNotFoundError(f"--from-local-val path not found: {local_val}")
        log(f"Local mode: sourcing JPEGs from {local_val} (Kaggle download skipped).")

    # 1) Ensure LOC_val_solution.csv is present
    log("Step 1/7: Ensuring LOC_val_solution.csv is present...")
    if not loc_csv.exists() and loc_zip.exists():
        unzip_if_needed(loc_zip, root)
    if not loc_csv.exists():
        raise FileNotFoundError(
            f"`{loc_csv}` not found. You should have it already. If not, download it with:\n"
            f"  kaggle competitions download -c {COMPETITION} -f LOC_val_solution.csv -p {root}"
        )

    # 2) Ensure mapping exists (user-created)
    log("Step 2/7: Loading LOC_synset_mapping.txt (wnid -> class_idx)...")
    wnid_to_idx = read_synset_mapping(mapping_path)

    # 3) Normalize folder layout
    log("Step 3/7: Normalizing folder layout (moving existing val JPEGs into data/)...")
    moved = move_existing_val_jpegs(root, data_dir)
    if moved:
        log(f"Moved {moved} existing JPEG(s) into {data_dir}")

    # 4) Balanced (stratified) sampling: per_class images for each of the 1000 classes
    log("Step 4/7: Balanced sampling and writing index CSVs...")
    items = read_loc_val_solution(loc_csv)
    samples = choose_samples_stratified(
        items, wnid_to_idx, per_class=args.per_class, seed=args.seed
    )
    total = len(samples)

    indices_csv = root / f"indices_{total}_seed{args.seed}.csv"
    write_indices_csv(samples, indices_csv)
    log(f"Wrote dev index CSV ({total} imgs, {args.per_class}/class): {indices_csv}")

    # Balanced 1000 (1/class) submission subset of the dev set
    submission = take_per_class(samples, 1)
    submission_csv = root / f"indices_{len(submission)}_seed{args.seed}.csv"
    if submission_csv != indices_csv:
        write_indices_csv(submission, submission_csv)
        log(f"Wrote submission index CSV ({len(submission)} imgs, 1/class): {submission_csv}")

    # 5) Clean up images outside the canonical set (handles "n>4" and old random samples)
    canonical_ids = {s.image_id for s in samples}
    if not args.no_clean:
        removed = cleanup_data_dir(data_dir, canonical_ids)
        log(f"Step 5/7: Cleanup removed {removed} JPEG(s) outside the canonical set.")
    else:
        log("Step 5/7: Cleanup skipped (--no-clean).")

    # 6) Materialize images into data/ — either copy from a local val dir (offline,
    #    no rate limit) or download per-file from Kaggle (round-robin + 429 backoff).
    failures: list[dict[str, str]] = []
    ok = 0
    skipped = 0

    if local_val is not None:
        log("Step 6/7: Copying sampled images from local val dir...")
        to_get = samples
        if args.max_download and args.max_download > 0:
            to_get = round_robin_order(samples)[: args.max_download]
            log(f"Smoke mode: only copying first {len(to_get)} images (from sampled list).")
        ok, skipped, failures = populate_from_local_val(
            to_get, local_val, data_dir, log_every=args.log_every
        )
    else:
        log("Step 6/7: Downloading missing images (round-robin, 429 backoff)...")
        to_get = round_robin_order(samples)
        if args.max_download and args.max_download > 0:
            to_get = to_get[: args.max_download]
            log(f"Smoke mode: only downloading first {len(to_get)} images (from sampled list).")

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
                max_retries=args.max_retries,
                backoff_base=args.backoff,
            )
            if success:
                ok += 1
            else:
                failures.append({"image_id": s.image_id, "wnid": s.wnid, "error": err or ""})

            if args.sleep > 0:
                time.sleep(args.sleep)

            if (i % 25) == 0:
                elapsed = time.time() - t0
                rate = (ok + skipped) / max(1.0, elapsed)
                log(f"Progress: [{i}/{len(to_get)}] ok={ok} skipped={skipped} fail={len(failures)} ({rate:.2f} img/s)")

    # 7) CIFAR-10 (separate dataset, separate folder)
    log("Step 7/7: CIFAR-10 test set...")
    cifar10_dir = Path(args.cifar10_dir).resolve()
    if args.skip_cifar10:
        log("CIFAR-10 download skipped (--skip-cifar10).")
    else:
        try:
            download_cifar10(cifar10_dir)
        except Exception as e:  # noqa: BLE001
            log(f"CIFAR-10 download failed: {e}")

    manifest = {
        "root": str(root),
        "source": "local" if local_val is not None else "kaggle",
        "from_local_val": str(local_val) if local_val is not None else None,
        "per_class": args.per_class,
        "n_samples": total,
        "seed": args.seed,
        "max_download": args.max_download,
        "moved_existing_jpegs": moved,
        "downloaded": ok,
        "skipped_existing": skipped,
        "failed": failures,
        "indices_csv": str(indices_csv),
        "submission_csv": str(submission_csv),
        "data_dir": str(data_dir),
        "cifar10_dir": str(cifar10_dir) if not args.skip_cifar10 else None,
        "elapsed_sec": round(time.time() - t0, 2),
    }
    (root / "download_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log("Done.")
    log(f"- dev indices:        {indices_csv}")
    log(f"- submission indices: {submission_csv}")
    log(f"- images:  {data_dir}  (downloaded {ok}, skipped {skipped}, failed {len(failures)})")
    if failures:
        log("Some downloads failed. Re-run the script to retry; it will skip existing JPEGs.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
