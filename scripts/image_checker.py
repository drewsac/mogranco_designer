#!/usr/bin/env python3
"""
Verify that every product in a catalog CSV has at least one corresponding image.

Expected image naming convention:

    <sku>.<frame>.<extension>

Examples:

    mg-p520-016-rc.1.jpg
    mg-p520-016-rc.2.jpg
    mg-p520-016-rc.3.jpg

An image named exactly "<sku>.<extension>" is also accepted.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that every product in a catalog CSV has one or more "
            "corresponding images."
        ),
        epilog=(
            "Images should be named using the product SKU, optionally followed "
            "by a frame number. Example: mg-p520-016-rc.1.jpg"
        ),
    )
    parser.add_argument(
        "catalog_csv",
        type=Path,
        help="Path to the product catalog CSV file.",
    )
    parser.add_argument(
        "image_directory",
        type=Path,
        help="Directory containing product images.",
    )
    parser.add_argument(
        "--sku-column",
        default="SKU",
        help='CSV column containing the SKU. Default: "SKU"',
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search image subdirectories recursively.",
    )
    return parser.parse_args()


def find_column(fieldnames: list[str], requested_name: str) -> str | None:
    """Find a CSV column name using a case-insensitive comparison."""
    requested = requested_name.strip().casefold()

    for fieldname in fieldnames:
        if fieldname.strip().casefold() == requested:
            return fieldname

    return None


def load_skus(catalog_path: Path, requested_column: str) -> list[tuple[int, str]]:
    """Return (CSV row number, SKU) pairs from the catalog."""
    try:
        csv_file = catalog_path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise RuntimeError(f"Could not open catalog CSV: {exc}") from exc

    with csv_file:
        reader = csv.DictReader(csv_file)

        if not reader.fieldnames:
            raise RuntimeError("The catalog CSV does not contain a header row.")

        sku_column = find_column(reader.fieldnames, requested_column)
        if sku_column is None:
            available = ", ".join(reader.fieldnames)
            raise RuntimeError(
                f'Could not find SKU column "{requested_column}". '
                f"Available columns: {available}"
            )

        skus: list[tuple[int, str]] = []

        # Header is row 1, so the first data row is row 2.
        for row_number, row in enumerate(reader, start=2):
            sku = (row.get(sku_column) or "").strip()

            if not sku:
                print(
                    f"WARNING: row {row_number} has no SKU and was skipped.",
                    file=sys.stderr,
                )
                continue

            skus.append((row_number, sku))

        return skus


def build_image_index(image_directory: Path, recursive: bool) -> set[str]:
    """
    Build a case-insensitive set of image filenames.

    Only supported image extensions are included.
    """
    iterator = image_directory.rglob("*") if recursive else image_directory.iterdir()
    filenames: set[str] = set()

    try:
        for path in iterator:
            if path.is_file() and path.suffix.casefold() in SUPPORTED_IMAGE_EXTENSIONS:
                filenames.add(path.name.casefold())
    except OSError as exc:
        raise RuntimeError(f"Could not read image directory: {exc}") from exc

    return filenames


def sku_has_image(sku: str, filenames: set[str]) -> bool:
    """
    Return True when an image filename matches either:

        <sku>.<extension>
        <sku>.<anything>.<extension>
    """
    sku_casefolded = sku.casefold()

    for filename in filenames:
        path = Path(filename)
        stem = path.stem

        if stem == sku_casefolded or stem.startswith(f"{sku_casefolded}."):
            return True

    return False


def main() -> int:
    args = parse_args()

    if not args.catalog_csv.is_file():
        print(
            f"ERROR: catalog CSV does not exist or is not a file: "
            f"{args.catalog_csv}",
            file=sys.stderr,
        )
        return 2

    if not args.image_directory.is_dir():
        print(
            f"ERROR: image directory does not exist or is not a directory: "
            f"{args.image_directory}",
            file=sys.stderr,
        )
        return 2

    try:
        skus = load_skus(args.catalog_csv, args.sku_column)
        image_filenames = build_image_index(
            args.image_directory,
            args.recursive,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not skus:
        print("ERROR: no products with SKUs were found in the catalog.", file=sys.stderr)
        return 2

    missing = [
        (row_number, sku)
        for row_number, sku in skus
        if not sku_has_image(sku, image_filenames)
    ]

    if missing:
        print(
            f"FAIL: {len(missing)} of {len(skus)} products have no corresponding image:"
        )
        for row_number, sku in missing:
            print(f"  row {row_number-1}: {sku}")
        return 1

    print(
        f"PASS: all {len(skus)} products have at least one corresponding image."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
