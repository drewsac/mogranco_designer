#!/usr/bin/env python3
"""
check_product_images.py

Validate that products in a catalog CSV have matching product images.

Expected image naming convention:
    sku.jpg
    sku.1.jpg
    sku.2.jpg
    sku.3.jpg

Examples:
    python3 scripts/check_product_images.py catalog/data/products.csv catalog/images/products

    python3 scripts/check_product_images.py catalog/data/products.csv catalog/images/products --recursive

    python3 scripts/check_product_images.py catalog/data/products.csv catalog/images/products --include-inactive
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".gif",
}


TRUE_VALUES = {"1", "true", "t", "yes", "y", "active", "enabled"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "inactive", "disabled"}


@dataclass(frozen=True)
class Product:
    row_number: int
    sku: str
    name: str
    active: bool


@dataclass(frozen=True)
class ImageMatch:
    image_path: Path
    matched_sku: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check that product rows in a CSV have matching image files, "
            "and that image files correspond to known product SKUs."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "catalog_csv",
        type=Path,
        help="Path to the product catalog CSV, for example catalog/data/products.csv.",
    )
    parser.add_argument(
        "image_dir",
        type=Path,
        help="Directory containing product images, for example catalog/images/products.",
    )

    parser.add_argument(
        "--sku-column",
        default=None,
        help=(
            "CSV column containing the SKU. If omitted, the script searches for "
            "common names such as sku, SKU, Item SKU, and Variation SKU."
        ),
    )
    parser.add_argument(
        "--name-column",
        default=None,
        help=(
            "CSV column containing the product name. If omitted, the script searches "
            "for common names such as name, Name, Item Name, and Product Name."
        ),
    )
    parser.add_argument(
        "--active-column",
        default=None,
        help=(
            "CSV column indicating whether a product is active. If omitted, the script "
            "searches for common names such as active, Active, and Enabled. If no active "
            "column is found, all products are treated as active."
        ),
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Require images for inactive products too.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search for images recursively under image_dir.",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use case-sensitive SKU/image matching.",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(DEFAULT_EXTENSIONS),
        help="Image file extensions to check.",
    )
    parser.add_argument(
        "--allow-orphan-images",
        action="store_true",
        help=(
            "Do not fail when image files do not match any known SKU. "
            "They will still be reported."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only summary information.",
    )

    return parser.parse_args()


def normalize(value: str, case_sensitive: bool) -> str:
    value = value.strip()
    return value if case_sensitive else value.lower()


def clean_header(value: str) -> str:
    return value.strip().replace("\ufeff", "")


def find_column(
    fieldnames: list[str],
    requested: str | None,
    candidates: Iterable[str],
    required: bool,
    label: str,
) -> str | None:
    cleaned = {clean_header(name): name for name in fieldnames}

    if requested:
        if requested in cleaned:
            return cleaned[requested]
        raise SystemExit(f"ERROR: Requested {label} column not found: {requested!r}")

    lowered = {clean_header(name).lower(): name for name in fieldnames}
    for candidate in candidates:
        match = lowered.get(candidate.lower())
        if match:
            return match

    if required:
        raise SystemExit(
            f"ERROR: Could not find {label} column. "
            f"Available columns: {', '.join(fieldnames)}"
        )

    return None


def parse_active(value: str) -> bool:
    cleaned = value.strip().lower()

    if cleaned == "":
        return True
    if cleaned in TRUE_VALUES:
        return True
    if cleaned in FALSE_VALUES:
        return False

    # Prefer keeping uncertain rows visible rather than silently dropping them.
    return True


def read_products(
    csv_path: Path,
    sku_column: str | None,
    name_column: str | None,
    active_column: str | None,
) -> tuple[list[Product], list[tuple[int, str]]]:
    if not csv_path.exists():
        raise SystemExit(f"ERROR: Catalog CSV does not exist: {csv_path}")
    if not csv_path.is_file():
        raise SystemExit(f"ERROR: Catalog CSV is not a file: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit(f"ERROR: CSV has no header row: {csv_path}")

        fieldnames = [clean_header(name) for name in reader.fieldnames]

        sku_col = find_column(
            fieldnames,
            sku_column,
            candidates=("sku", "SKU", "Item SKU", "Variation SKU"),
            required=True,
            label="SKU",
        )
        name_col = find_column(
            fieldnames,
            name_column,
            candidates=("name", "Name", "Item Name", "Product Name", "Product"),
            required=False,
            label="name",
        )
        active_col = find_column(
            fieldnames,
            active_column,
            candidates=("active", "Active", "Enabled", "Is Active", "Published"),
            required=False,
            label="active",
        )

        products: list[Product] = []
        missing_sku_rows: list[tuple[int, str]] = []

        for row_index, row in enumerate(reader, start=2):
            sku = (row.get(sku_col) or "").strip()
            name = (row.get(name_col) or "").strip() if name_col else ""
            active = parse_active(row.get(active_col) or "") if active_col else True

            if not sku:
                missing_sku_rows.append((row_index, name))
                continue

            products.append(
                Product(
                    row_number=row_index,
                    sku=sku,
                    name=name,
                    active=active,
                )
            )

    return products, missing_sku_rows


def normalize_extensions(values: Iterable[str]) -> set[str]:
    extensions: set[str] = set()
    for value in values:
        ext = value.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        extensions.add(ext)
    return extensions


def find_image_files(image_dir: Path, recursive: bool, extensions: set[str]) -> list[Path]:
    if not image_dir.exists():
        raise SystemExit(f"ERROR: Image directory does not exist: {image_dir}")
    if not image_dir.is_dir():
        raise SystemExit(f"ERROR: Image path is not a directory: {image_dir}")

    iterator = image_dir.rglob("*") if recursive else image_dir.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in extensions
    )


def match_image_to_sku(
    image_path: Path,
    known_skus: set[str],
    case_sensitive: bool,
) -> str | None:
    stem = normalize(image_path.stem, case_sensitive)

    # Supported forms:
    #   sku.jpg
    #   sku.1.jpg
    #   sku.2.jpg
    #
    # We intentionally do not treat "sku-main.jpg" as a match by default because
    # hyphens are already common inside SKUs.
    possible_skus = [stem]
    if "." in stem:
        possible_skus.append(stem.rsplit(".", 1)[0])

    for possible_sku in possible_skus:
        if possible_sku in known_skus:
            return possible_sku

    return None


def print_heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> int:
    args = parse_args()

    products, missing_sku_rows = read_products(
        args.catalog_csv,
        sku_column=args.sku_column,
        name_column=args.name_column,
        active_column=args.active_column,
    )

    normalized_to_original: dict[str, str] = {}
    sku_counts: Counter[str] = Counter()

    for product in products:
        normalized_sku = normalize(product.sku, args.case_sensitive)
        sku_counts[normalized_sku] += 1
        normalized_to_original.setdefault(normalized_sku, product.sku)

    duplicate_skus = {
        normalized_sku: count
        for normalized_sku, count in sku_counts.items()
        if count > 1
    }

    products_to_check = [
        product for product in products if args.include_inactive or product.active
    ]

    known_skus = set(sku_counts.keys())

    image_files = find_image_files(
        args.image_dir,
        recursive=args.recursive,
        extensions=normalize_extensions(args.extensions),
    )

    images_by_sku: dict[str, list[Path]] = defaultdict(list)
    orphan_images: list[Path] = []

    for image_path in image_files:
        matched_sku = match_image_to_sku(
            image_path,
            known_skus=known_skus,
            case_sensitive=args.case_sensitive,
        )
        if matched_sku is None:
            orphan_images.append(image_path)
        else:
            images_by_sku[matched_sku].append(image_path)

    missing_images: list[Product] = []
    for product in products_to_check:
        normalized_sku = normalize(product.sku, args.case_sensitive)
        if not images_by_sku.get(normalized_sku):
            missing_images.append(product)

    print("Product image check")
    print("===================")
    print(f"Catalog CSV:       {args.catalog_csv}")
    print(f"Image directory:   {args.image_dir}")
    print(f"Products read:     {len(products)}")
    print(f"Products checked:  {len(products_to_check)}")
    print(f"Images found:      {len(image_files)}")
    print(f"Matched images:    {sum(len(paths) for paths in images_by_sku.values())}")
    print(f"Missing images:    {len(missing_images)}")
    print(f"Orphan images:     {len(orphan_images)}")
    print(f"Rows missing SKU:  {len(missing_sku_rows)}")
    print(f"Duplicate SKUs:    {len(duplicate_skus)}")

    if not args.quiet:
        if missing_images:
            print_heading("Products missing images")
            for product in missing_images:
                label = f" — {product.name}" if product.name else ""
                inactive = "" if product.active else " [inactive]"
                print(f"row {product.row_number}: {product.sku}{label}{inactive}")

        if orphan_images:
            print_heading("Images not matching any known SKU")
            for path in orphan_images:
                print(path)

        if missing_sku_rows:
            print_heading("CSV rows missing SKU")
            for row_number, name in missing_sku_rows:
                label = f" — {name}" if name else ""
                print(f"row {row_number}{label}")

        if duplicate_skus:
            print_heading("Duplicate SKUs")
            for normalized_sku, count in sorted(duplicate_skus.items()):
                original = normalized_to_original.get(normalized_sku, normalized_sku)
                print(f"{original}: {count} rows")

    failure_count = 0
    failure_count += len(missing_images)
    failure_count += len(missing_sku_rows)
    failure_count += len(duplicate_skus)
    if not args.allow_orphan_images:
        failure_count += len(orphan_images)

    if failure_count:
        print()
        print("FAIL: catalog image check found problems.")
        return 1

    print()
    print("PASS: every checked product has at least one matching image.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
