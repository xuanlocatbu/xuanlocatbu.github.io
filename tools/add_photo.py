#!/usr/bin/env python3
"""Add a photo with a caption to the Photos page.

Usage:
  .venv/bin/python tools/add_photo.py ~/Downloads/IMG_1234.jpg "Me after my 20-minute run"

The photo is rotated upright, resized for the web, and saved WITHOUT its
metadata (phone photos usually contain the GPS location where they were taken).
New photos appear at the top of the page.
"""
import argparse
import html
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "photos"
INDEX = PHOTOS / "index.html"
MAX_SIZE = 1600
MARKER = "<!-- PHOTOS:START -->"


def unique_name(caption):
    slug = re.sub(r"[^a-z0-9]+", "-", caption.lower()).strip("-")[:50].strip("-") or "photo"
    name, n = slug, 2
    while (PHOTOS / f"{name}.jpg").exists():
        name, n = f"{slug}-{n}", n + 1
    return f"{name}.jpg"


def main():
    parser = argparse.ArgumentParser(description="Add a photo with a caption.")
    parser.add_argument("image", type=Path, help="path to the photo (JPG or PNG; HEIC is not supported)")
    parser.add_argument("caption", help="caption shown under the photo")
    args = parser.parse_args()

    if not args.image.exists():
        sys.exit(f"Can't find {args.image}")

    image = ImageOps.exif_transpose(Image.open(args.image)).convert("RGB")
    image.thumbnail((MAX_SIZE, MAX_SIZE), Image.LANCZOS)
    filename = unique_name(args.caption)
    image.save(PHOTOS / filename, quality=85, optimize=True)  # no exif passed, so metadata is dropped

    caption = html.escape(args.caption, quote=True)
    figure = f"""
      <figure class="photo">
        <a href="{filename}" target="_blank" rel="noopener"><img src="{filename}" alt="{caption}" width="{image.width}" height="{image.height}" loading="lazy"></a>
        <figcaption>{caption}</figcaption>
      </figure>"""

    index = INDEX.read_text(encoding="utf-8")
    pos = index.index(MARKER) + len(MARKER)
    INDEX.write_text(index[:pos] + figure + index[pos:], encoding="utf-8")
    print(f"Added photos/{filename}")


if __name__ == "__main__":
    main()
