# Catalog field definitions

The product catalog should be good enough to support store browsing, room-photo recommendations, and eventual Square import/export work.

## Required field

`name`  
The customer-facing product name. This is the only required field.

## Product identity fields

`sku`  
Internal Mogranco SKU. If this exists, it is the best unique identifier.

`vendor_name`  
The manufacturer, rep group, or vendor name.

`vendor_sku`  
The vendor's item number, stock code, or product ID.

`brand`  
Customer-facing brand/manufacturer when different from vendor.

## Product description fields

`description`  
Short description suitable for the app.

`category`  
Use a readable path such as `Lighting > Table Lamps` or `Furniture > Tables > Console Tables`.

`color`, `material`, `finish`  
Simple descriptive fields. Use plain language.

`notes`  
Internal notes. Not necessarily customer-facing.

## Pricing fields

`price`  
Retail price in dollars, such as `425.00`.

`cost`  
Store cost in dollars, if known.

## Dimension fields

`width_in`, `depth_in`, `height_in`, `diameter_in`  
Measurements in inches. Use numbers only where possible.

## Tag fields

Tags should be separated with semicolons.

Good:

```text
living room; bedroom; entry
```

Avoid commas for tags because vendor/product text often contains commas.

`room_tags`  
Where the product fits: `living room`, `bedroom`, `entry`, `dining room`, `powder bath`, `office`.

`style_tags`  
Design vocabulary: `traditional`, `transitional`, `coastal`, `organic modern`, `cottage`, `classic`.

`product_tags`  
Object vocabulary: `lamp`, `table lamp`, `pillow`, `mirror`, `vase`, `console table`.

`general_tags`  
Other useful descriptors: `statement piece`, `soft lighting`, `shelf styling`, `accent`.

## Media field

`image_url`  
Optional product image URL for now. Local image support can be added later.

## Status field

`active`  
Use `yes` or `no`. Inactive products stay in the database but are hidden from normal list/search commands unless requested.
