#!/usr/bin/env python3
"""Prepare YOLOv8 training data for the Smart City garbage-dumping detector.

Ingests one or more manually-downloaded YOLOv8-format exports placed under
``ml/data/raw/`` (e.g. Roboflow Universe exports and/or TACO converted to
YOLO format), remaps their class names to the 4 canonical classes, drops
near-duplicate images, and writes an 80/10/10 train/val/test split into
``ml/data/{train,val,test}/{images,labels}``. Finally it refreshes
``ml/dataset.yaml``.

Dependencies: Python stdlib + Pillow + PyYAML + numpy only. No roboflow SDK.

Each raw export is expected to look like a standard YOLOv8 export::

    <export>/
        data.yaml            # contains a `names:` list/dict (optional)
        train/images/*.jpg   # or images/ at any depth
        train/labels/*.txt
        valid/... test/...   # any subset of splits

Image/label pairing is by stem; labels live in a sibling ``labels`` dir.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import random
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import yaml
from PIL import Image

# --------------------------------------------------------------------------- #
# Canonical contract: class order is FIXED. Must match dataset.yaml /
# app/detector.py / CONTRACT.md. Do not reorder.
# --------------------------------------------------------------------------- #
CANONICAL_CLASSES: List[str] = [
    "garbage_pile",
    "garbage_bag",
    "litter",
    "overflowing_bin",
]
CLASS_TO_INDEX: Dict[str, int] = {n: i for i, n in enumerate(CANONICAL_CLASSES)}

# Configurable mapping from raw/source class names (lowercased, stripped) to a
# canonical class. Edit this to cover the label vocabulary of the datasets you
# actually downloaded. Source names not present here are dropped (with a warn)
# unless they already match a canonical name.
CLASS_NAME_MAP: Dict[str, str] = {
    # garbage_pile
    "garbage_pile": "garbage_pile",
    "garbage": "garbage_pile",
    "trash": "garbage_pile",
    "trash_pile": "garbage_pile",
    "garbage pile": "garbage_pile",
    "dump": "garbage_pile",
    "illegal_dumping": "garbage_pile",
    "garbage_dump": "garbage_pile",
    "waste": "garbage_pile",
    "rubbish": "garbage_pile",
    # garbage_bag
    "garbage_bag": "garbage_bag",
    "garbage bag": "garbage_bag",
    "trash_bag": "garbage_bag",
    "plastic_bag": "garbage_bag",
    "bag": "garbage_bag",
    "sack": "garbage_bag",
    # litter
    "litter": "litter",
    "scattered_litter": "litter",
    "plastic": "litter",
    "bottle": "litter",
    "can": "litter",
    "cup": "litter",
    "wrapper": "litter",
    "cardboard": "litter",
    "paper": "litter",
    "cigarette": "litter",
    "debris": "litter",
    # overflowing_bin
    "overflowing_bin": "overflowing_bin",
    "overflowing bin": "overflowing_bin",
    "overflow_bin": "overflowing_bin",
    "full_bin": "overflowing_bin",
    "overflowing_dustbin": "overflowing_bin",
    "bin": "overflowing_bin",
    "dustbin": "overflowing_bin",
    "garbage_bin": "overflowing_bin",
    "trash_bin": "overflowing_bin",
    "dumpster": "overflowing_bin",
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

log = logging.getLogger("prepare_data")


class MalformedLabelError(RuntimeError):
    """Raised when a YOLO label file cannot be parsed. Fail loud."""


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def load_source_names(export_root: Path) -> Optional[List[str]]:
    """Read the `names` list from a YOLO export's data.yaml, if present."""
    for cand in ("data.yaml", "dataset.yaml", "data.yml"):
        f = export_root / cand
        if not f.is_file():
            continue
        try:
            doc = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            log.warning("Could not parse %s: %s", f, exc)
            return None
        names = doc.get("names")
        if isinstance(names, dict):
            # {0: 'a', 1: 'b'} -> ordered list
            return [names[k] for k in sorted(names, key=int)]
        if isinstance(names, list):
            return names
    return None


def find_label_for_image(img: Path) -> Optional[Path]:
    """Locate the YOLO label .txt for an image by swapping images->labels."""
    parts = list(img.parts)
    # Replace the last 'images' path segment with 'labels'.
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "images":
            parts[i] = "labels"
            lbl = Path(*parts).with_suffix(".txt")
            return lbl
    # Fallback: sibling labels dir.
    lbl = img.parent.parent / "labels" / (img.stem + ".txt")
    return lbl if lbl.exists() else None


def discover_pairs(export_root: Path) -> List[Tuple[Path, Optional[Path]]]:
    """Find all (image, label) pairs under an export root."""
    pairs: List[Tuple[Path, Optional[Path]]] = []
    for img in sorted(export_root.rglob("*")):
        if img.suffix.lower() not in IMAGE_EXTS or not img.is_file():
            continue
        if "images" not in img.parts:
            # Skip stray images outside an images/ dir to avoid grabbing
            # unrelated assets (logos, previews, etc.).
            continue
        pairs.append((img, find_label_for_image(img)))
    return pairs


# --------------------------------------------------------------------------- #
# Label remapping
# --------------------------------------------------------------------------- #
def _norm(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def remap_label_file(
    label_path: Path,
    source_names: Optional[List[str]],
    unmapped: Counter,
) -> Optional[str]:
    """Read a YOLO label file and return remapped content (canonical indices).

    Returns the new label text (possibly empty if all objects were dropped),
    or ``None`` if the file is empty/whitespace. Raises on malformed lines.
    """
    raw = label_path.read_text().strip()
    if not raw:
        return None

    out_lines: List[str] = []
    for lineno, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        toks = line.split()
        if len(toks) < 5:
            raise MalformedLabelError(
                f"{label_path}:{lineno}: expected >=5 tokens, got {len(toks)}: {line!r}"
            )
        try:
            src_idx = int(float(toks[0]))
            coords = [float(t) for t in toks[1:5]]
        except ValueError as exc:
            raise MalformedLabelError(
                f"{label_path}:{lineno}: non-numeric token: {line!r} ({exc})"
            ) from exc
        for c in coords:
            if not (0.0 <= c <= 1.0):
                raise MalformedLabelError(
                    f"{label_path}:{lineno}: coord out of [0,1] range: {c} in {line!r}"
                )

        # Resolve source class name.
        if source_names is not None:
            if not (0 <= src_idx < len(source_names)):
                raise MalformedLabelError(
                    f"{label_path}:{lineno}: class index {src_idx} out of range "
                    f"for {len(source_names)} source names"
                )
            src_name = source_names[src_idx]
        else:
            # No names file: assume already-canonical index ordering.
            if not (0 <= src_idx < len(CANONICAL_CLASSES)):
                raise MalformedLabelError(
                    f"{label_path}:{lineno}: class index {src_idx} out of range and "
                    f"no source names available to remap"
                )
            src_name = CANONICAL_CLASSES[src_idx]

        canon = CLASS_NAME_MAP.get(_norm(src_name))
        if canon is None and src_name in CLASS_TO_INDEX:
            canon = src_name
        if canon is None:
            unmapped[src_name] += 1
            continue  # drop objects we cannot map

        new_idx = CLASS_TO_INDEX[canon]
        # Keep any extra tokens (e.g. segmentation) only for the box case; we
        # standardise to the 5-token detection format.
        out_lines.append(f"{new_idx} {coords[0]:.6f} {coords[1]:.6f} "
                         f"{coords[2]:.6f} {coords[3]:.6f}")
    return "\n".join(out_lines)


# --------------------------------------------------------------------------- #
# Dedup
# --------------------------------------------------------------------------- #
def perceptual_hash(img_path: Path, hash_size: int = 16) -> Optional[str]:
    """Cheap average-hash for near-duplicate detection (stdlib + Pillow/numpy).

    Returns a hex string, or None if the image cannot be read.
    """
    try:
        with Image.open(img_path) as im:
            im = im.convert("L").resize((hash_size, hash_size), Image.BILINEAR)
            arr = np.asarray(im, dtype=np.float32)
    except Exception as exc:  # noqa: BLE001 - corrupt image, skip gracefully
        log.warning("Cannot hash %s: %s", img_path, exc)
        return None
    bits = (arr > arr.mean()).flatten()
    # Pack bits into bytes -> hex.
    packed = np.packbits(bits)
    return packed.tobytes().hex()


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def collect_dataset(raw_dir: Path) -> List[Tuple[Path, Optional[Path], Optional[List[str]]]]:
    """Walk raw_dir for export roots and gather (image, label, source_names)."""
    # An "export root" is any dir directly under raw/, plus raw/ itself.
    roots: List[Path] = [raw_dir]
    roots += [d for d in sorted(raw_dir.iterdir()) if d.is_dir()]

    seen_roots: set = set()
    items: List[Tuple[Path, Optional[Path], Optional[List[str]]]] = []
    for root in roots:
        names = load_source_names(root)
        pairs = discover_pairs(root)
        if not pairs:
            continue
        # Avoid double-counting when a child root's images were already swept
        # by the parent. We tag by image path uniqueness later, so just gather.
        for img, lbl in pairs:
            items.append((img, lbl, names))
        seen_roots.add(root)
        log.info("Export %-40s images=%-5d names=%s",
                 root.name or root, len(pairs),
                 names if names else "(assume canonical order)")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare YOLOv8 garbage-detection data from raw exports.")
    parser.add_argument(
        "--raw-dir", type=Path, default=Path(__file__).parent / "data" / "raw",
        help="Directory containing manually-downloaded YOLOv8 exports.")
    parser.add_argument(
        "--out-dir", type=Path, default=Path(__file__).parent / "data",
        help="Output dataset root (train/val/test created here).")
    parser.add_argument(
        "--yaml-path", type=Path, default=Path(__file__).parent / "dataset.yaml",
        help="Path to dataset.yaml to (re)write.")
    parser.add_argument("--train", type=float, default=0.8, help="Train fraction.")
    parser.add_argument("--val", type=float, default=0.1, help="Val fraction.")
    parser.add_argument("--test", type=float, default=0.1, help="Test fraction.")
    parser.add_argument(
        "--dedup-threshold", type=int, default=0,
        help="Max Hamming distance to treat two images as duplicates "
             "(0 = exact average-hash match only).")
    parser.add_argument("--seed", type=int, default=42, help="Split RNG seed.")
    parser.add_argument(
        "--keep-empty", action="store_true",
        help="Keep images whose labels become empty after remapping "
             "(useful as background/negatives).")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Analyse and report only; do not write the split.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    total = args.train + args.val + args.test
    if abs(total - 1.0) > 1e-6:
        log.error("Split fractions must sum to 1.0 (got %.3f)", total)
        return 2

    raw_dir: Path = args.raw_dir
    if not raw_dir.is_dir():
        log.error("Raw dir not found: %s -- download exports first (see README).",
                  raw_dir)
        return 2

    log.info("Scanning %s", raw_dir)
    items = collect_dataset(raw_dir)
    if not items:
        log.error("No (image,label) pairs found under %s. Did you unzip a "
                  "YOLOv8 export into ml/data/raw/ ?", raw_dir)
        return 2
    log.info("Discovered %d candidate images across exports.", len(items))

    # ---- Dedup + remap ----
    unmapped: Counter = Counter()
    class_counts: Counter = Counter()
    hashes: Dict[str, Path] = {}
    kept: List[Tuple[Path, str]] = []  # (image_path, remapped_label_text)
    n_dup = n_nolabel = n_empty = n_badhash = 0

    for img, lbl, names in items:
        h = perceptual_hash(img)
        if h is None:
            n_badhash += 1
            continue
        if h in hashes:
            n_dup += 1
            log.debug("Duplicate: %s ~= %s", img.name, hashes[h].name)
            continue

        if lbl is None or not lbl.exists():
            n_nolabel += 1
            log.debug("No label for %s -- skipping.", img.name)
            continue

        # Fail loud on malformed labels.
        remapped = remap_label_file(lbl, names, unmapped)
        if not remapped:
            if args.keep_empty:
                hashes[h] = img
                kept.append((img, ""))
            else:
                n_empty += 1
            continue

        for line in remapped.splitlines():
            class_counts[int(line.split()[0])] += 1
        hashes[h] = img
        kept.append((img, remapped))

    log.info("Unique kept=%d | dup=%d | no-label=%d | empty-after-remap=%d | "
             "unreadable=%d", len(kept), n_dup, n_nolabel, n_empty, n_badhash)
    if unmapped:
        log.warning("Dropped objects from %d unmapped source classes: %s",
                    len(unmapped), dict(unmapped.most_common()))
    log.info("Canonical class object counts: %s",
             {CANONICAL_CLASSES[i]: class_counts.get(i, 0)
              for i in range(len(CANONICAL_CLASSES))})

    if not kept:
        log.error("Nothing to write after filtering. Check CLASS_NAME_MAP.")
        return 1

    # ---- Split ----
    rng = random.Random(args.seed)
    rng.shuffle(kept)
    n = len(kept)
    n_train = int(n * args.train)
    n_val = int(n * args.val)
    splits = {
        "train": kept[:n_train],
        "val": kept[n_train:n_train + n_val],
        "test": kept[n_train + n_val:],
    }
    log.info("Split: train=%d val=%d test=%d",
             len(splits["train"]), len(splits["val"]), len(splits["test"]))

    if args.dry_run:
        log.info("Dry run complete -- no files written.")
        return 0

    # ---- Write ----
    out: Path = args.out_dir
    for split in splits:
        for sub in ("images", "labels"):
            d = out / split / sub
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)

    for split, rows in splits.items():
        for idx, (img, label_text) in enumerate(rows):
            stem = f"{img.stem}_{idx:06d}"
            dst_img = out / split / "images" / (stem + img.suffix.lower())
            dst_lbl = out / split / "labels" / (stem + ".txt")
            shutil.copy2(img, dst_img)
            dst_lbl.write_text(label_text + ("\n" if label_text else ""))
    log.info("Wrote split into %s", out)

    # ---- Refresh dataset.yaml ----
    write_dataset_yaml(args.yaml_path, out)
    log.info("Refreshed %s", args.yaml_path)
    log.info("Done.")
    return 0


def write_dataset_yaml(yaml_path: Path, data_root: Path) -> None:
    """Write dataset.yaml with canonical names and split paths.

    ``path`` is made relative to the yaml file's directory when possible so the
    config stays portable (matches the committed default of ``path: data``).
    """
    try:
        rel = data_root.resolve().relative_to(yaml_path.resolve().parent)
        path_val = str(rel)
    except ValueError:
        path_val = str(data_root.resolve())

    names_block = "".join(
        f"  {i}: {name}\n" for i, name in enumerate(CANONICAL_CLASSES))
    content = (
        "# Smart City - Illegal Garbage Dumping Detection\n"
        "# Auto-generated by ml/prepare_data.py. Class order is FIXED\n"
        "# (must match app/detector.py and CONTRACT.md). Do not reorder.\n\n"
        f"path: {path_val}\n"
        "train: train/images\n"
        "val: val/images\n"
        "test: test/images\n\n"
        "names:\n"
        f"{names_block}\n"
        f"nc: {len(CANONICAL_CLASSES)}\n"
    )
    yaml_path.write_text(content)


if __name__ == "__main__":
    sys.exit(main())
