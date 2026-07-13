#!/usr/bin/env python3
"""
Export the catalog CSV into static JSON for the product browser.

The CSV remains the source of truth. This script writes generated browser assets
under app/public so Vite can serve them in development and include them in builds.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_CSV = ROOT / "catalog" / "data" / "products.csv"
DEFAULT_IMAGE_DIR = ROOT / "catalog" / "data" / "images" / "products"
DEFAULT_OUTPUT_JSON = ROOT / "app" / "public" / "data" / "products.json"
DEFAULT_PUBLIC_IMAGE_DIR = ROOT / "app" / "public" / "product-images"

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
TEXT_FIELDS = (
    "name",
    "description",
    "sku",
    "vendor_name",
    "vendor_sku",
    "brand",
    "category",
    "color",
    "material",
    "finish",
    "image_url",
    "active",
    "notes",
)
NUMBER_FIELDS = (
    "price",
    "cost",
    "width_in",
    "depth_in",
    "height_in",
    "diameter_in",
)
TAG_FIELDS = ("room_tags", "style_tags", "product_tags", "general_tags")
FALSE_VALUES = {"0", "false", "f", "no", "n", "inactive", "disabled"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export catalog/data/products.csv to app/public/data/products.json."
    )
    parser.add_argument("--catalog-csv", type=Path, default=DEFAULT_CATALOG_CSV)
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--public-image-dir", type=Path, default=DEFAULT_PUBLIC_IMAGE_DIR)
    parser.add_argument(
        "--public-image-path",
        default="/product-images",
        help="Browser path prefix for copied product images.",
    )
    return parser.parse_args()


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def parse_number(value: object) -> float | None:
    text = clean(value).replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_active(value: object) -> bool:
    text = clean(value).lower()
    return text not in FALSE_VALUES


def split_tags(value: object) -> list[str]:
    text = clean(value)
    if not text:
        return []

    normalized = text.replace("|", ";").replace(">", ";")
    return sorted({part.strip() for part in normalized.split(";") if part.strip()})


def read_catalog(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        raise SystemExit(f"ERROR: Catalog CSV does not exist: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit(f"ERROR: Catalog CSV has no header row: {csv_path}")
        return [dict(row) for row in reader]


def image_candidates(sku: str) -> Iterable[str]:
    for ext in IMAGE_EXTENSIONS:
        yield f"{sku}{ext}"
    for ext in IMAGE_EXTENSIONS:
        yield f"{sku}.1{ext}"


def build_image_index(image_dir: Path) -> dict[str, Path]:
    if not image_dir.is_dir():
        raise SystemExit(f"ERROR: Product image directory does not exist: {image_dir}")

    return {
        path.name.lower(): path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }


def resolve_image(
    row: dict[str, str],
    image_index: dict[str, Path],
    public_image_dir: Path,
    public_image_path: str,
) -> str:
    image_url = clean(row.get("image_url"))
    if image_url:
        return image_url

    sku = clean(row.get("sku")).lower()
    if not sku:
        return ""

    for candidate in image_candidates(sku):
        source = image_index.get(candidate.lower())
        if source:
            public_image_dir.mkdir(parents=True, exist_ok=True)
            destination = public_image_dir / source.name
            shutil.copy2(source, destination)
            return f"{public_image_path.rstrip('/')}/{destination.name}"

    return ""


def normalize_product(
    row: dict[str, str],
    image_index: dict[str, Path],
    public_image_dir: Path,
    public_image_path: str,
) -> dict[str, object]:
    product: dict[str, object] = {}

    for field in TEXT_FIELDS:
        product[field] = clean(row.get(field))

    for field in NUMBER_FIELDS:
        product[field] = parse_number(row.get(field))

    for field in TAG_FIELDS:
        product[field] = split_tags(row.get(field))

    product["active"] = parse_active(row.get("active"))
    product["image_src"] = resolve_image(
        row,
        image_index=image_index,
        public_image_dir=public_image_dir,
        public_image_path=public_image_path,
    )

    return product


def main() -> int:
    args = parse_args()
    rows = read_catalog(args.catalog_csv)
    image_index = build_image_index(args.image_dir)

    products = [
        normalize_product(
            row,
            image_index=image_index,
            public_image_dir=args.public_image_dir,
            public_image_path=args.public_image_path,
        )
        for row in rows
    ]

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with args.output_json.open("w", encoding="utf-8") as handle:
        json.dump(products, handle, indent=2)
        handle.write("\n")

    missing_images = sum(1 for product in products if not product["image_src"])
    print(f"Exported products: {len(products)}")
    print(f"Output JSON: {args.output_json}")
    print(f"Public images: {args.public_image_dir}")
    print(f"Products without resolved image: {missing_images}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
