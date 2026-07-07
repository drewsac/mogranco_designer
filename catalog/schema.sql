PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    sku TEXT,
    vendor_name TEXT,
    vendor_sku TEXT,
    brand TEXT,
    category TEXT,
    price_cents INTEGER,
    cost_cents INTEGER,
    currency TEXT NOT NULL DEFAULT 'USD',
    width_in REAL,
    depth_in REAL,
    height_in REAL,
    diameter_in REAL,
    color TEXT,
    material TEXT,
    finish TEXT,
    image_url TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'manual',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_products_sku
ON products(sku)
WHERE sku IS NOT NULL AND sku != '';

CREATE UNIQUE INDEX IF NOT EXISTS ux_products_vendor_sku
ON products(vendor_name, vendor_sku)
WHERE vendor_name IS NOT NULL AND vendor_name != ''
  AND vendor_sku IS NOT NULL AND vendor_sku != '';

CREATE INDEX IF NOT EXISTS ix_products_name ON products(name);
CREATE INDEX IF NOT EXISTS ix_products_category ON products(category);
CREATE INDEX IF NOT EXISTS ix_products_vendor ON products(vendor_name);
CREATE INDEX IF NOT EXISTS ix_products_active ON products(active);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tag_type TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, tag_type)
);

CREATE TABLE IF NOT EXISTS product_tags (
    product_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (product_id, tag_id),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE VIEW IF NOT EXISTS product_catalog_view AS
SELECT
    p.id,
    p.name,
    p.description,
    p.sku,
    p.vendor_name,
    p.vendor_sku,
    p.brand,
    p.category,
    printf('%.2f', COALESCE(p.price_cents, 0) / 100.0) AS price,
    printf('%.2f', COALESCE(p.cost_cents, 0) / 100.0) AS cost,
    p.currency,
    p.width_in,
    p.depth_in,
    p.height_in,
    p.diameter_in,
    p.color,
    p.material,
    p.finish,
    p.image_url,
    p.active,
    p.source,
    p.notes,
    p.created_at,
    p.updated_at,
    GROUP_CONCAT(CASE WHEN t.tag_type = 'room' THEN t.name END, '; ') AS room_tags,
    GROUP_CONCAT(CASE WHEN t.tag_type = 'style' THEN t.name END, '; ') AS style_tags,
    GROUP_CONCAT(CASE WHEN t.tag_type = 'product' THEN t.name END, '; ') AS product_tags,
    GROUP_CONCAT(CASE WHEN t.tag_type = 'general' THEN t.name END, '; ') AS general_tags
FROM products p
LEFT JOIN product_tags pt ON pt.product_id = p.id
LEFT JOIN tags t ON t.id = pt.tag_id
GROUP BY p.id;
