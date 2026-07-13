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
  import_catalog_to_supabase.py
app/
  public/
    data/products.json          # generated
    product-images/             # generated
  src/
supabase/
  migrations/
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

## Supabase Catalog Prep

The first Supabase migration is in:

```text
supabase/migrations/202607130001_catalog_schema.sql
```

It creates:

- `products` for catalog rows imported from CSV.
- `product_images` for every SKU-matched image frame.
- a public `product-images` storage bucket for customer-facing catalog images.
- read-only public policies for active products and their images.

The browser still reads generated static JSON until the Supabase client is wired
in a later step.

Copy `.env.example` to `.env` when you are ready to use Supabase credentials.
Do not commit real keys. Browser code should only use:

```text
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
```

Trusted import scripts may use:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Never expose the service-role key in browser code.

Acceptance check for this stage:

1. Apply the migration to a Supabase project.
2. Confirm the `products` and `product_images` tables exist.
3. Confirm the `product-images` bucket exists and is public.
4. Confirm anonymous users can select active products but cannot insert or update
   catalog rows.

## Supabase Catalog Import

The trusted importer is:

```text
scripts/import_catalog_to_supabase.py
```

It reads the current CSV, discovers all SKU-named image frames, and upserts
catalog records into Supabase. It is safe to run locally first because dry-run
mode is the default:

```powershell
python scripts\import_catalog_to_supabase.py
```

Expected current dry-run result:

```text
Products ready:  66
Images ready:    93
Skipped rows:    0
Orphan images:   0
```

After the migration is applied and `.env` contains real trusted credentials,
run:

```powershell
python scripts\import_catalog_to_supabase.py --apply
```

The importer needs these trusted values:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

The service-role key bypasses Row Level Security for importing. Keep it only in
local/server-side environments and never put it in browser code.
