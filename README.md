# Mogranco Designer

Mogranco Designer is the current proof of concept for a Modern Grace & Co.
catalog browser. The CSV catalog remains the product source of truth; the
browser reads generated static JSON.

## Current Structure

```text
catalog/
  catalog_cli.py
  schema.sql
  data/
    products.csv
    catalog.sqlite
    images/products/
scripts/
  check_product_images.py
  export_products_json.py
app/
  public/
    data/products.json          # generated
    product-images/             # generated
  src/
```

## Validate Catalog Images

The product images currently live in `catalog/data/images/products`.

```bash
python3 scripts/check_product_images.py catalog/data/products.csv catalog/data/images/products
```

On Windows, use `python` instead of `python3` if the `python3` launcher is not
available:

```powershell
python scripts\check_product_images.py catalog\data\products.csv catalog\data\images\products
```

## Export Products JSON

Run this after changing `catalog/data/products.csv` or product images:

```bash
python3 scripts/export_products_json.py
```

Windows equivalent:

```powershell
python scripts\export_products_json.py
```

This writes `app/public/data/products.json` and copies resolved browser images
into `app/public/product-images`.

## Start The Product Browser

```bash
cd app
npm install
npm run dev
```

If PowerShell blocks `npm.ps1`, use `npm.cmd`:

```powershell
cd app
npm.cmd install
npm.cmd run dev
```

Vite will print a local URL, usually `http://localhost:5173/`.

## Build

```bash
cd app
npm run build
```
