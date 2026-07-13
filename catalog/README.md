# Mogranco Catalog POC

This is the first buildable piece of the Mogranco App: a local product catalog that is independent of Square.

The goal is not to solve every inventory problem yet. The goal is to create a clean product source of truth that can be manually seeded with 50–70 real Modern Grace & Co products, searched, exported, and later connected to the mobile-first web app.

## What this includes

- SQLite database schema for products and tags
- CSV import workflow for manual product seeding
- CSV export workflow
- Search by product name, description, vendor, category, or tags
- Simple stats to see catalog coverage
- No external Python dependencies

## Folder layout

```text
mogranco_catalog/
  catalog_cli.py              # command-line app
  schema.sql                  # SQLite schema
  data/
    product_template.csv      # blank CSV import template
    sample_products.csv       # demo seed data
  docs/
    catalog_fields.md         # field definitions
    next_steps.md             # recommended next build steps
```

## First run

From inside this folder:

```bash
python3 catalog_cli.py init
python3 catalog_cli.py import-csv data/sample_products.csv
python3 catalog_cli.py list
python3 catalog_cli.py search lamp
python3 catalog_cli.py stats
```

The default database will be created here:

```text
data/catalog.sqlite
```

## Start entering real products

Use this file as your working CSV:

```text
data/product_template.csv
```

You can copy it to something like:

```bash
cp data/product_template.csv data/mogranco_seed_001.csv
```

Then fill in real product rows and import them:

```bash
python3 catalog_cli.py import-csv data/mogranco_seed_001.csv
```

The import is an upsert. If a row has the same `sku`, it updates the existing product. If there is no SKU, it falls back to matching on `vendor_name` + `vendor_sku`.

## Useful commands

List active products:

```bash
python3 catalog_cli.py list
```

Search by product name, description, vendor, category, or tag:

```bash
python3 catalog_cli.py search "lamp"
python3 catalog_cli.py search "living room"
python3 catalog_cli.py search "brass"
```

Show one product by SKU or vendor SKU:

```bash
python3 catalog_cli.py show MG-DEMO-002
```

Export the catalog:

```bash
python3 catalog_cli.py export-csv data/catalog_export.csv
```

Write a fresh blank template:

```bash
python3 catalog_cli.py write-template data/new_products.csv
```

Use a different database file:

```bash
python3 catalog_cli.py --db data/test_catalog.sqlite init
python3 catalog_cli.py --db data/test_catalog.sqlite import-csv data/sample_products.csv
```

## Recommended first real-data target

Seed 20–50 products across these buckets:

- 5–10 table lamps
- 5–10 pillows/textiles
- 5–10 tabletop decor pieces
- 5–10 mirrors/wall decor pieces
- 5–10 furniture pieces

That gives the recommendation engine enough variety to start producing useful room suggestions.
