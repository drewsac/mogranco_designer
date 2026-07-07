# Next steps after the catalog POC

## Step 1: Replace demo data with real products

Start with 20–50 real Modern Grace & Co products. Keep the first pass simple. Good product coverage is more important than perfect data.

Suggested first categories:

- Lighting > Table Lamps
- Textiles > Pillows
- Decor > Vases
- Decor > Mirrors
- Furniture > Tables

## Step 2: Add product images

For the POC, the easiest path is to store image URLs in `image_url`.

Later options:

- Store images in a local `/static/product-images` folder
- Store images in cloud object storage
- Pull images from vendor data when available

## Step 3: Add a tiny API

Once the data is seeded, the next build step should be a small API with endpoints like:

```text
GET /products
GET /products/{id}
GET /search?q=lamp
GET /recommendations?room=living-room&style=transitional
```

## Step 4: Build basic recommendations

Start with tag matching, not AI.

Example:

A room photo or user text produces tags like:

```text
living room, transitional, brass, lamp, mirror
```

The app searches the catalog for products with overlapping room/style/product/color/material tags.

## Step 5: Add AI interpretation

After the tag-based version works, add AI to interpret user text and/or room photos into normalized catalog search tags.
