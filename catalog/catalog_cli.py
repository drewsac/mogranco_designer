#!/usr/bin/env python3
"""
Mogranco product catalog CLI.

A small SQLite-backed catalog intended for the Mogranco App POC.
It is independent of Square and designed to be seeded manually from CSV.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

DEFAULT_DB = Path("data/catalog.sqlite")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

CSV_FIELDS = [
    "name",
    "description",
    "sku",
    "vendor_name",
    "vendor_sku",
    "brand",
    "category",
    "price",
    "cost",
    "width_in",
    "depth_in",
    "height_in",
    "diameter_in",
    "color",
    "material",
    "finish",
    "room_tags",
    "style_tags",
    "product_tags",
    "general_tags",
    "image_url",
    "active",
    "notes",
]

PRODUCT_COLUMNS = [
    "id",
    "name",
    "description",
    "sku",
    "vendor_name",
    "vendor_sku",
    "brand",
    "category",
    "price_cents",
    "cost_cents",
    "currency",
    "width_in",
    "depth_in",
    "height_in",
    "diameter_in",
    "color",
    "material",
    "finish",
    "image_url",
    "active",
    "source",
    "notes",
]


@dataclass(frozen=True)
class ImportResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema)
    print(f"Initialized catalog database: {db_path}")


def clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def parse_money(value: object) -> int | None:
    text = clean(value)
    if text is None:
        return None
    text = text.replace("$", "").replace(",", "")
    try:
        dollars = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid money value: {value!r}") from exc
    cents = (dollars * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def parse_float(value: object) -> float | None:
    text = clean(value)
    if text is None:
        return None
    text = text.replace('"', "").replace("in", "").strip()
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Invalid number value: {value!r}") from exc


def parse_bool(value: object, default: bool = True) -> int:
    text = clean(value)
    if text is None:
        return int(default)
    normalized = text.lower()
    if normalized in {"1", "true", "yes", "y", "active"}:
        return 1
    if normalized in {"0", "false", "no", "n", "inactive"}:
        return 0
    raise ValueError(f"Invalid active value: {value!r}. Use yes/no or true/false.")


def split_tags(value: object) -> list[str]:
    text = clean(value)
    if text is None:
        return []
    # Semicolon is preferred because product/vendor names often contain commas.
    raw_items = text.replace("|", ";").split(";")
    return sorted({item.strip().lower() for item in raw_items if item.strip()})


def product_payload(row: dict[str, str]) -> dict[str, object]:
    name = clean(row.get("name"))
    if not name:
        raise ValueError("Missing required field: name")

    return {
        "id": clean(row.get("id")) or str(uuid.uuid4()),
        "name": name,
        "description": clean(row.get("description")),
        "sku": clean(row.get("sku")),
        "vendor_name": clean(row.get("vendor_name")),
        "vendor_sku": clean(row.get("vendor_sku")),
        "brand": clean(row.get("brand")),
        "category": clean(row.get("category")),
        "price_cents": parse_money(row.get("price")),
        "cost_cents": parse_money(row.get("cost")),
        "currency": "USD",
        "width_in": parse_float(row.get("width_in")),
        "depth_in": parse_float(row.get("depth_in")),
        "height_in": parse_float(row.get("height_in")),
        "diameter_in": parse_float(row.get("diameter_in")),
        "color": clean(row.get("color")),
        "material": clean(row.get("material")),
        "finish": clean(row.get("finish")),
        "image_url": clean(row.get("image_url")),
        "active": parse_bool(row.get("active"), default=True),
        "source": "csv",
        "notes": clean(row.get("notes")),
    }


def find_existing_product_id(conn: sqlite3.Connection, payload: dict[str, object]) -> str | None:
    sku = payload.get("sku")
    if sku:
        row = conn.execute("SELECT id FROM products WHERE sku = ?", (sku,)).fetchone()
        if row:
            return str(row["id"])

    vendor_name = payload.get("vendor_name")
    vendor_sku = payload.get("vendor_sku")
    if vendor_name and vendor_sku:
        row = conn.execute(
            "SELECT id FROM products WHERE vendor_name = ? AND vendor_sku = ?",
            (vendor_name, vendor_sku),
        ).fetchone()
        if row:
            return str(row["id"])

    return None


def upsert_product(conn: sqlite3.Connection, payload: dict[str, object]) -> tuple[str, bool]:
    existing_id = find_existing_product_id(conn, payload)
    if existing_id:
        payload = {**payload, "id": existing_id}
        set_columns = [column for column in PRODUCT_COLUMNS if column != "id"]
        assignments = ", ".join([f"{column} = :{column}" for column in set_columns])
        conn.execute(
            f"""
            UPDATE products
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
            """,
            payload,
        )
        return existing_id, False

    placeholders = ", ".join([f":{column}" for column in PRODUCT_COLUMNS])
    columns = ", ".join(PRODUCT_COLUMNS)
    conn.execute(
        f"INSERT INTO products ({columns}) VALUES ({placeholders})",
        payload,
    )
    return str(payload["id"]), True


def set_tags(conn: sqlite3.Connection, product_id: str, tags_by_type: dict[str, Iterable[str]]) -> None:
    conn.execute("DELETE FROM product_tags WHERE product_id = ?", (product_id,))
    for tag_type, names in tags_by_type.items():
        for name in names:
            conn.execute(
                "INSERT OR IGNORE INTO tags (name, tag_type) VALUES (?, ?)",
                (name, tag_type),
            )
            tag_row = conn.execute(
                "SELECT id FROM tags WHERE name = ? AND tag_type = ?",
                (name, tag_type),
            ).fetchone()
            if tag_row:
                conn.execute(
                    "INSERT OR IGNORE INTO product_tags (product_id, tag_id) VALUES (?, ?)",
                    (product_id, tag_row["id"]),
                )


def import_csv(db_path: Path, csv_path: Path) -> ImportResult:
    init_db(db_path)
    inserted = updated = skipped = 0

    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle, connect(db_path) as conn:
        reader = csv.DictReader(handle)
        missing_required_header = "name" not in (reader.fieldnames or [])
        if missing_required_header:
            raise ValueError("CSV must include a 'name' column.")

        for line_number, row in enumerate(reader, start=2):
            try:
                payload = product_payload(row)
                product_id, was_inserted = upsert_product(conn, payload)
                set_tags(
                    conn,
                    product_id,
                    {
                        "room": split_tags(row.get("room_tags")),
                        "style": split_tags(row.get("style_tags")),
                        "product": split_tags(row.get("product_tags")),
                        "general": split_tags(row.get("general_tags")),
                    },
                )
                if was_inserted:
                    inserted += 1
                else:
                    updated += 1
            except Exception as exc:  # Keep import moving while reporting bad rows.
                skipped += 1
                print(f"Skipped row {line_number}: {exc}", file=sys.stderr)

    return ImportResult(inserted=inserted, updated=updated, skipped=skipped)


def format_money(cents: int | None) -> str:
    if cents is None:
        return ""
    return f"${cents / 100:.2f}"


def list_products(db_path: Path, limit: int, include_inactive: bool) -> None:
    where = "" if include_inactive else "WHERE active = 1"
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT id, name, sku, vendor_name, vendor_sku, category, price_cents, active
            FROM products
            {where}
            ORDER BY updated_at DESC, name COLLATE NOCASE
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    print_table(rows, ["name", "sku", "vendor_name", "vendor_sku", "category", "price", "active"])


def search_products(db_path: Path, query: str, limit: int, include_inactive: bool) -> None:
    search = f"%{query.lower()}%"
    active_clause = "" if include_inactive else "AND p.active = 1"
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT p.id, p.name, p.sku, p.vendor_name, p.vendor_sku, p.category, p.price_cents, p.active
            FROM products p
            LEFT JOIN product_tags pt ON pt.product_id = p.id
            LEFT JOIN tags t ON t.id = pt.tag_id
            WHERE (
                lower(p.name) LIKE ?
                OR lower(COALESCE(p.description, '')) LIKE ?
                OR lower(COALESCE(p.category, '')) LIKE ?
                OR lower(COALESCE(p.vendor_name, '')) LIKE ?
                OR lower(COALESCE(t.name, '')) LIKE ?
            )
            {active_clause}
            ORDER BY p.name COLLATE NOCASE
            LIMIT ?
            """,
            (search, search, search, search, search, limit),
        ).fetchall()
    print_table(rows, ["name", "sku", "vendor_name", "vendor_sku", "category", "price", "active"])


def show_product(db_path: Path, product_id_or_sku: str) -> None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM product_catalog_view
            WHERE id = ? OR sku = ? OR vendor_sku = ?
            LIMIT 1
            """,
            (product_id_or_sku, product_id_or_sku, product_id_or_sku),
        ).fetchone()

    if not row:
        print(f"No product found for: {product_id_or_sku}")
        return

    for key in row.keys():
        value = row[key]
        if value is not None and value != "":
            print(f"{key}: {value}")


def export_csv(db_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM product_catalog_view ORDER BY name COLLATE NOCASE").fetchall()

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if not rows:
            writer.writerow(CSV_FIELDS)
            print(f"Exported empty template: {output_path}")
            return
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow([row[key] for key in row.keys()])

    print(f"Exported {len(rows)} products: {output_path}")


def write_template(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
    print(f"Wrote CSV template: {output_path}")


def stats(db_path: Path) -> None:
    with connect(db_path) as conn:
        product_count = conn.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"]
        active_count = conn.execute("SELECT COUNT(*) AS count FROM products WHERE active = 1").fetchone()["count"]
        vendor_count = conn.execute(
            "SELECT COUNT(DISTINCT vendor_name) AS count FROM products WHERE vendor_name IS NOT NULL AND vendor_name != ''"
        ).fetchone()["count"]
        category_rows = conn.execute(
            """
            SELECT category, COUNT(*) AS count
            FROM products
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY count DESC, category COLLATE NOCASE
            LIMIT 20
            """
        ).fetchall()
        tag_rows = conn.execute(
            """
            SELECT tag_type, COUNT(*) AS count
            FROM tags
            GROUP BY tag_type
            ORDER BY tag_type
            """
        ).fetchall()

    print(f"Products: {product_count}")
    print(f"Active products: {active_count}")
    print(f"Vendors: {vendor_count}")
    print("\nCategories:")
    print_table(category_rows, ["category", "count"])
    print("\nTags:")
    print_table(tag_rows, ["tag_type", "count"])


def print_table(rows: Iterable[sqlite3.Row], columns: list[str]) -> None:
    rows = list(rows)
    if not rows:
        print("No rows.")
        return

    rendered: list[dict[str, str]] = []
    for row in rows:
        item: dict[str, str] = {}
        for column in columns:
            if column == "price":
                item[column] = format_money(row["price_cents"])
            elif column == "active":
                item[column] = "yes" if row["active"] else "no"
            else:
                value = row[column]
                item[column] = "" if value is None else str(value)
        rendered.append(item)

    widths = {
        column: max(len(column), *(len(item[column]) for item in rendered))
        for column in columns
    }
    header = "  ".join(column.ljust(widths[column]) for column in columns)
    print(header)
    print("  ".join("-" * widths[column] for column in columns))
    for item in rendered:
        print("  ".join(item[column].ljust(widths[column]) for column in columns))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mogranco product catalog CLI")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database path. Default: {DEFAULT_DB}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create or update the catalog database schema")

    import_parser = subparsers.add_parser("import-csv", help="Import products from CSV")
    import_parser.add_argument("csv_path", type=Path)

    list_parser = subparsers.add_parser("list", help="List products")
    list_parser.add_argument("--limit", type=int, default=25)
    list_parser.add_argument("--include-inactive", action="store_true")

    search_parser = subparsers.add_parser("search", help="Search products by name, description, vendor, category, or tag")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=25)
    search_parser.add_argument("--include-inactive", action="store_true")

    show_parser = subparsers.add_parser("show", help="Show one product by id, SKU, or vendor SKU")
    show_parser.add_argument("id_or_sku")

    export_parser = subparsers.add_parser("export-csv", help="Export catalog to CSV")
    export_parser.add_argument("output_path", type=Path)

    template_parser = subparsers.add_parser("write-template", help="Write a blank import CSV template")
    template_parser.add_argument("output_path", type=Path)

    subparsers.add_parser("stats", help="Show catalog summary stats")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            init_db(args.db)
        elif args.command == "import-csv":
            result = import_csv(args.db, args.csv_path)
            print(f"Import complete. Inserted: {result.inserted}. Updated: {result.updated}. Skipped: {result.skipped}.")
        elif args.command == "list":
            list_products(args.db, args.limit, args.include_inactive)
        elif args.command == "search":
            search_products(args.db, args.query, args.limit, args.include_inactive)
        elif args.command == "show":
            show_product(args.db, args.id_or_sku)
        elif args.command == "export-csv":
            export_csv(args.db, args.output_path)
        elif args.command == "write-template":
            write_template(args.output_path)
        elif args.command == "stats":
            stats(args.db)
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
