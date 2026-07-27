import { createClient } from "@supabase/supabase-js";

export type Product = {
  id: string;
  name: string;
  description: string;
  sku: string;
  vendor_name: string;
  vendor_sku: string;
  brand: string;
  category: string;
  price: number | null;
  cost: number | null;
  width_in: number | null;
  depth_in: number | null;
  height_in: number | null;
  diameter_in: number | null;
  color: string;
  material: string;
  finish: string;
  room_tags: string[];
  style_tags: string[];
  product_tags: string[];
  general_tags: string[];
  image_url: string;
  image_src: string;
  active: boolean;
  notes: string;
};

type SupabaseProductRow = {
  id: string;
  name: string;
  description: string | null;
  sku: string | null;
  vendor_name: string | null;
  vendor_sku: string | null;
  brand: string | null;
  category: string | null;
  price_cents: number | null;
  cost_cents: number | null;
  width_in: number | string | null;
  depth_in: number | string | null;
  height_in: number | string | null;
  diameter_in: number | string | null;
  color: string | null;
  material: string | null;
  finish: string | null;
  room_tags: string[] | null;
  style_tags: string[] | null;
  product_tags: string[] | null;
  general_tags: string[] | null;
  active: boolean;
  notes: string | null;
  product_images: Array<{
    public_url: string | null;
    storage_bucket: string;
    storage_path: string;
    is_primary: boolean;
    sort_order: number;
  }> | null;
};

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseKey = (
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
  import.meta.env.VITE_SUPABASE_ANON_KEY
) as string | undefined;

const supabase =
  supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null;

function text(value: string | null | undefined): string {
  return value ?? "";
}

function numberValue(value: number | string | null): number | null {
  if (value === null) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function centsToDollars(value: number | null): number | null {
  return value === null ? null : value / 100;
}

function imageSource(row: SupabaseProductRow): string {
  const images = row.product_images ?? [];
  const primary =
    images.find((image) => image.is_primary) ??
    [...images].sort((a, b) => a.sort_order - b.sort_order)[0];

  return primary?.public_url ?? "";
}

function mapSupabaseProduct(row: SupabaseProductRow): Product {
  return {
    id: row.id,
    name: row.name,
    description: text(row.description),
    sku: text(row.sku),
    vendor_name: text(row.vendor_name),
    vendor_sku: text(row.vendor_sku),
    brand: text(row.brand),
    category: text(row.category),
    price: centsToDollars(row.price_cents),
    cost: centsToDollars(row.cost_cents),
    width_in: numberValue(row.width_in),
    depth_in: numberValue(row.depth_in),
    height_in: numberValue(row.height_in),
    diameter_in: numberValue(row.diameter_in),
    color: text(row.color),
    material: text(row.material),
    finish: text(row.finish),
    room_tags: row.room_tags ?? [],
    style_tags: row.style_tags ?? [],
    product_tags: row.product_tags ?? [],
    general_tags: row.general_tags ?? [],
    image_url: imageSource(row),
    image_src: imageSource(row),
    active: row.active,
    notes: text(row.notes),
  };
}

async function fetchStaticProducts(): Promise<Product[]> {
  const response = await fetch("/data/products.json");
  if (!response.ok) {
    throw new Error(`Could not load products.json (${response.status})`);
  }

  const products = (await response.json()) as Product[];
  return products
    .filter((product) => product.active)
    .map((product) => ({ ...product, id: product.id || product.sku }));
}

async function fetchSupabaseProducts(): Promise<Product[]> {
  if (!supabase) {
    throw new Error("Supabase environment variables are not configured.");
  }

  const { data, error } = await supabase
    .from("products")
    .select(
      `
      id,
      name,
      description,
      sku,
      vendor_name,
      vendor_sku,
      brand,
      category,
      price_cents,
      cost_cents,
      width_in,
      depth_in,
      height_in,
      diameter_in,
      color,
      material,
      finish,
      room_tags,
      style_tags,
      product_tags,
      general_tags,
      active,
      notes,
      product_images (
        public_url,
        storage_bucket,
        storage_path,
        is_primary,
        sort_order
      )
    `,
    )
    .eq("active", true)
    .order("name", { ascending: true });

  if (error) {
    throw new Error(error.message);
  }

  return (data ?? []).map((row) => mapSupabaseProduct(row as SupabaseProductRow));
}

export async function fetchProducts(): Promise<Product[]> {
  if (!supabase) {
    return fetchStaticProducts();
  }

  try {
    const products = await fetchSupabaseProducts();
    return products.length > 0 ? products : fetchStaticProducts();
  } catch (error) {
    console.warn("Supabase catalog fetch failed; falling back to static JSON.", error);
    return fetchStaticProducts();
  }
}
