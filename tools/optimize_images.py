#!/usr/bin/env python3
"""Strip image metadata and resize for GitHub README usage.

- Processes all images in a directory (non-recursive by default).
- Removes EXIF and other metadata where possible.
- Resizes down to fit within a max bounding box (no upscaling).
- Only rewrites files when changes are required.

Typical use:
  python tools/optimize_images.py images --max-size 1600
  python tools/optimize_images.py images --dry-run

Requires:
  pip install pillow
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class Plan:
    max_size: int
    quality: int
    optimize: bool
    progressive: bool
    dry_run: bool
    recursive: bool


def iter_images(root: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        iterator = root.rglob("*")
    else:
        iterator = root.glob("*")

    for path in iterator:
        if not path.is_file():
            continue
        if path.suffix.lower() in SUPPORTED_EXTS:
            yield path


def has_metadata(image: Image.Image) -> bool:
    # JPEG/TIFF EXIF
    try:
        exif = image.getexif()
        if exif is not None and len(exif) > 0:
            return True
    except Exception:
        pass

    # Other formats (PNG text chunks, etc.)
    # Pillow stores ancillary info in image.info
    info = getattr(image, "info", None) or {}
    # Common keys: icc_profile, gamma, dpi, exif, xml, Description, parameters...
    # We treat any non-empty info as metadata worth stripping.
    return len(info) > 0


def resized_dimensions(width: int, height: int, max_size: int) -> tuple[int, int]:
    if width <= max_size and height <= max_size:
        return width, height

    if width >= height:
        new_w = max_size
        new_h = max(1, round(height * (max_size / width)))
    else:
        new_h = max_size
        new_w = max(1, round(width * (max_size / height)))

    return new_w, new_h


def strip_and_resize(path: Path, plan: Plan) -> tuple[bool, str]:
    # Returns (changed, message)
    with Image.open(path) as im:
        im.load()

        original_w, original_h = im.size
        needs_resize = (original_w > plan.max_size) or (original_h > plan.max_size)
        needs_strip = has_metadata(im)

        if not (needs_resize or needs_strip):
            return False, "ok (no changes needed)"

        # Ensure pixels are detached from original container to avoid carrying metadata.
        out = im.copy()

        # Normalize orientation (EXIF) into pixels, then drop EXIF.
        try:
            out = ImageOps.exif_transpose(out)  # type: ignore[name-defined]
        except Exception:
            # ImageOps may not be available in very old Pillow; ignore.
            pass

        new_w, new_h = resized_dimensions(out.width, out.height, plan.max_size)
        if (new_w, new_h) != (out.width, out.height):
            out = out.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)

        suffix = path.suffix.lower()
        save_kwargs: dict = {}

        # Remove metadata by not passing exif/icc/etc. and by clearing info.
        out.info.clear()

        if suffix in {".jpg", ".jpeg"}:
            save_kwargs.update(
                format="JPEG",
                quality=plan.quality,
                optimize=plan.optimize,
                progressive=plan.progressive,
                subsampling="4:2:0",
            )
            # Ensure common modes for JPEG
            if out.mode not in {"RGB", "L"}:
                out = out.convert("RGB")
        elif suffix == ".png":
            save_kwargs.update(
                format="PNG",
                optimize=plan.optimize,
            )
        elif suffix == ".webp":
            save_kwargs.update(
                format="WEBP",
                quality=plan.quality,
                method=6,
            )
        else:
            # Fallback; shouldn’t happen due to SUPPORTED_EXTS
            save_kwargs.update(format=im.format)

        # Write atomically
        tmp_path = path.with_suffix(path.suffix + ".tmp")

        if plan.dry_run:
            msg = []
            if needs_strip:
                msg.append("strip-metadata")
            if needs_resize:
                msg.append(f"resize {original_w}x{original_h} -> {out.width}x{out.height}")
            return True, "would " + ", ".join(msg)

        out.save(tmp_path, **save_kwargs)
        os.replace(tmp_path, path)

        msg = []
        if needs_strip:
            msg.append("stripped metadata")
        if needs_resize:
            msg.append(f"resized {original_w}x{original_h} -> {out.width}x{out.height}")
        return True, ", ".join(msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strip image metadata and resize for GitHub READMEs")
    parser.add_argument(
        "path",
        nargs="?",
        default="images",
        help="Folder containing images (default: images)",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=1600,
        help="Max width/height in pixels (default: 1600)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=85,
        help="JPEG/WebP quality (default: 85)",
    )
    parser.add_argument(
        "--no-optimize",
        action="store_true",
        help="Disable encoder optimizations",
    )
    parser.add_argument(
        "--no-progressive",
        action="store_true",
        help="Disable progressive JPEG",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Process images recursively",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    root = Path(args.path)
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    plan = Plan(
        max_size=max(1, args.max_size),
        quality=min(100, max(1, args.quality)),
        optimize=not args.no_optimize,
        progressive=not args.no_progressive,
        dry_run=bool(args.dry_run),
        recursive=bool(args.recursive),
    )

    paths = list(iter_images(root, recursive=plan.recursive))
    if not paths:
        print(f"No images found in {root}")
        return 0

    changed = 0
    skipped = 0

    for path in sorted(paths):
        try:
            did_change, message = strip_and_resize(path, plan)
        except Exception as exc:
            print(f"ERROR {path}: {exc}")
            continue

        if did_change:
            changed += 1
            print(f"CHANGED {path}: {message}")
        else:
            skipped += 1
            print(f"OK {path}: {message}")

    print(f"\nDone. changed={changed}, ok={skipped}, total={len(paths)}")
    return 0


if __name__ == "__main__":
    # Optional import for EXIF orientation handling; keep it here to avoid hard dependency issues.
    try:
        from PIL import ImageOps  # noqa: F401
    except Exception:
        ImageOps = None  # type: ignore[assignment]

    raise SystemExit(main())
