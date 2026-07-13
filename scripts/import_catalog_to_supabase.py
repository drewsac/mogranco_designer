#!/usr/bin/env python3
"""
Import the CSV catalog and SKU-named product images into Supabase.

The script is dry-run by default. Pass --apply only after the Supabase migration
has been applied and SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are configured.
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_CSV = ROOT / "catalog" / "data" / "products.csv"
DEFAULT_IMAGE_DIR = ROOT / "catalog" / "data" / "images" / "products"
DEFAULT_BUCKET = "product-images"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "inactive", "disabled"}
TRUE_VALUES = {"1", "true", "t", "yes", "y", "active", "enabled"}


@dataclass(frozen=True)
class ProductImport:
    row_number: int
    payload: dict[str, object]


@dataclass(frozen=True)
class ImageImport:
    sku: str
    frame_number: int
    sort_order: int
    path: Path
    storage_path: str


@dataclass(frozen=True)
class ImportSummary:
    products: int
    images: int
    skipped_rows: int
    orphan_images: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import catalog CSV rows and SKU-named images into Supabase."
    )
    parser.add_argument("--catalog-csv", type=Path, default=DEFAULT_CATALOG_CSV)
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform Supabase writes. Without this flag, only prints a dry-run summary.",
    )
    return parser.parse_args()


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def none_if_blank(value: object) -> str | None:
    text = clean(value)
    return text or None


def parse_money_cents(value: object) -> int | None:
    text = clean(value).replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        dollars = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid money value: {value!r}") from exc
    return int((dollars * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_decimal_text(value: object) -> str | None:
    text = clean(value).replace('"', "").replace("in", "").strip()
    if not text:
        return None
    try:
        return str(Decimal(text))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid dimension value: {value!r}") from exc


def parse_active(value: object) -> bool:
    text = clean(value).lower()
    if not text:
        return True
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return True


def split_tags(value: object) -> list[str]:
    text = clean(value)
    if not text:
        return []
    normalized = text.replace("|", ";").replace(">", ";")
    return sorted({part.strip() for part in normalized.split(";") if part.strip()})


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def read_products(csv_path: Path) -> tuple[list[ProductImport], list[str]]:
    if not csv_path.is_file():
        raise SystemExit(f"ERROR: Catalog CSV does not exist: {csv_path}")

    products: list[ProductImport] = []
    skipped: list[str] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit(f"ERROR: Catalog CSV has no header row: {csv_path}")

        for row_number, row in enumerate(reader, start=2):
            try:
                name = clean(row.get("name"))
                sku = none_if_blank(row.get("sku"))
                vendor_name = none_if_blank(row.get("vendor_name"))
                vendor_sku = none_if_blank(row.get("vendor_sku"))

                if not name:
                    raise ValueError("missing name")
                if not sku and not (vendor_name and vendor_sku):
                    raise ValueError("missing SKU and vendor identity")

                payload: dict[str, object] = {
                    "name": name,
                    "description": none_if_blank(row.get("description")),
                    "sku": sku,
                    "vendor_name": vendor_name,
                    "vendor_sku": vendor_sku,
                    "brand": none_if_blank(row.get("brand")),
                    "category": none_if_blank(row.get("category")),
                    "price_cents": parse_money_cents(row.get("price")),
                    "cost_cents": parse_money_cents(row.get("cost")),
                    "currency": "USD",
                    "width_in": parse_decimal_text(row.get("width_in")),
                    "depth_in": parse_decimal_text(row.get("depth_in")),
                    "height_in": parse_decimal_text(row.get("height_in")),
                    "diameter_in": parse_decimal_text(row.get("diameter_in")),
                    "color": none_if_blank(row.get("color")),
                    "material": none_if_blank(row.get("material")),
                    "finish": none_if_blank(row.get("finish")),
                    "room_tags": split_tags(row.get("room_tags")),
                    "style_tags": split_tags(row.get("style_tags")),
                    "product_tags": split_tags(row.get("product_tags")),
                    "general_tags": split_tags(row.get("general_tags")),
                    "active": parse_active(row.get("active")),
                    "source": "csv",
                    "notes": none_if_blank(row.get("notes")),
                }
                products.append(ProductImport(row_number=row_number, payload=payload))
            except ValueError as exc:
                skipped.append(f"row {row_number}: {exc}")

    return products, skipped


def normalize_sku(value: str) -> str:
    return value.strip().lower()


def storage_safe_sku(value: str) -> str:
    normalized = normalize_sku(value)
    return re.sub(r"[^a-z0-9._-]+", "-", normalized).strip("-") or "unknown-sku"


def parse_image_filename(path: Path, known_skus: set[str]) -> tuple[str, int] | None:
    stem = path.stem.lower()
    candidates: list[tuple[str, int]] = [(stem, 0)]
    if "." in stem:
        possible_sku, possible_frame = stem.rsplit(".", 1)
        if possible_frame.isdigit():
            candidates.append((possible_sku, int(possible_frame)))

    for sku, frame_number in candidates:
        if sku in known_skus:
            return sku, frame_number
    return None


def discover_images(image_dir: Path, products: Iterable[ProductImport]) -> tuple[list[ImageImport], list[Path]]:
    if not image_dir.is_dir():
        raise SystemExit(f"ERROR: Product image directory does not exist: {image_dir}")

    known_skus = {
        normalize_sku(str(product.payload["sku"]))
        for product in products
        if product.payload.get("sku")
    }

    images: list[ImageImport] = []
    orphans: list[Path] = []
    for path in sorted(image_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        match = parse_image_filename(path, known_skus)
        if not match:
            orphans.append(path)
            continue
        sku, frame_number = match
        sort_order = frame_number
        storage_path = f"products/{storage_safe_sku(sku)}/{frame_number}{path.suffix.lower()}"
        images.append(
            ImageImport(
                sku=sku,
                frame_number=frame_number,
                sort_order=sort_order,
                path=path,
                storage_path=storage_path,
            )
        )

    return images, orphans


class SupabaseClient:
    def __init__(self, url: str, service_role_key: str) -> None:
        self.url = url.rstrip("/")
        self.service_role_key = service_role_key

    @classmethod
    def from_env(cls) -> "SupabaseClient":
        url = clean(os.environ.get("SUPABASE_URL"))
        key = clean(os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
        if not url or not key:
            raise SystemExit(
                "ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required with --apply."
            )
        return cls(url=url, service_role_key=key)

    def request_json(
        self,
        method: str,
        path: str,
        body: object | None = None,
        query: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> object:
        encoded_query = f"?{parse.urlencode(query)}" if query else ""
        url = f"{self.url}{path}{encoded_query}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
        return json.loads(raw) if raw else None

    def upload_file(self, bucket: str, storage_path: str, path: Path) -> str:
        quoted_path = parse.quote(storage_path, safe="/")
        url = f"{self.url}/storage/v1/object/{bucket}/{quoted_path}"
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        req = request.Request(
            url,
            data=path.read_bytes(),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as response:
                response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"upload {path} failed: {exc.code} {detail}") from exc
        return f"{self.url}/storage/v1/object/public/{bucket}/{quoted_path}"

    def upsert_product(self, payload: dict[str, object]) -> dict[str, object]:
        on_conflict = "sku" if payload.get("sku") else "vendor_name,vendor_sku"
        result = self.request_json(
            "POST",
            "/rest/v1/products",
            body=payload,
            query={"on_conflict": on_conflict},
            extra_headers={"Prefer": "resolution=merge-duplicates,return=representation"},
        )
        if not isinstance(result, list) or not result:
            raise RuntimeError(f"Supabase did not return product row for {payload.get('sku')}")
        product = result[0]
        if not isinstance(product, dict):
            raise RuntimeError(f"Unexpected product response: {product!r}")
        return product

    def upsert_product_image(self, payload: dict[str, object]) -> None:
        self.request_json(
            "POST",
            "/rest/v1/product_images",
            body=payload,
            query={"on_conflict": "product_id,frame_number"},
            extra_headers={"Prefer": "resolution=merge-duplicates"},
        )


def print_dry_run(products: list[ProductImport], images: list[ImageImport], skipped: list[str], orphans: list[Path]) -> None:
    print("Supabase catalog import dry run")
    print("===============================")
    print(f"Products ready:  {len(products)}")
    print(f"Images ready:    {len(images)}")
    print(f"Skipped rows:    {len(skipped)}")
    print(f"Orphan images:   {len(orphans)}")

    if skipped:
        print()
        print("Skipped rows")
        print("------------")
        for item in skipped:
            print(item)

    if orphans:
        print()
        print("Images not matching any SKU")
        print("---------------------------")
        for path in orphans:
            print(path)

    print()
    print("No Supabase writes performed. Pass --apply to import.")


def apply_import(
    client: SupabaseClient,
    bucket: str,
    products: list[ProductImport],
    images: list[ImageImport],
) -> ImportSummary:
    products_by_sku: dict[str, dict[str, object]] = {}
    for product_import in products:
        product = client.upsert_product(product_import.payload)
        sku = clean(product.get("sku")).lower()
        if sku:
            products_by_sku[sku] = product

    images_by_sku: dict[str, list[ImageImport]] = {}
    for image in images:
        images_by_sku.setdefault(image.sku, []).append(image)

    uploaded = 0
    for sku, product_images in images_by_sku.items():
        product = products_by_sku.get(sku)
        if not product:
            continue

        primary_frame = min(image.frame_number for image in product_images)
        for image in product_images:
            public_url = client.upload_file(bucket, image.storage_path, image.path)
            client.upsert_product_image(
                {
                    "product_id": product["id"],
                    "sku": product.get("sku") or image.sku,
                    "frame_number": image.frame_number,
                    "sort_order": image.sort_order,
                    "storage_bucket": bucket,
                    "storage_path": image.storage_path,
                    "public_url": public_url,
                    "original_filename": image.path.name,
                    "content_type": mimetypes.guess_type(image.path.name)[0],
                    "size_bytes": image.path.stat().st_size,
                    "is_primary": image.frame_number == primary_frame,
                }
            )
            uploaded += 1

    return ImportSummary(
        products=len(products),
        images=uploaded,
        skipped_rows=0,
        orphan_images=0,
    )


def main() -> int:
    args = parse_args()
    load_env_file(args.env_file)

    products, skipped = read_products(args.catalog_csv)
    images, orphans = discover_images(args.image_dir, products)

    if not args.apply:
        print_dry_run(products, images, skipped, orphans)
        return 0 if not skipped and not orphans else 1

    if skipped or orphans:
        print_dry_run(products, images, skipped, orphans)
        print()
        print("ERROR: Fix skipped rows or orphan images before running with --apply.")
        return 1

    client = SupabaseClient.from_env()
    summary = apply_import(client, args.bucket, products, images)

    print("Supabase catalog import complete")
    print("================================")
    print(f"Products upserted: {summary.products}")
    print(f"Images uploaded:   {summary.images}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
