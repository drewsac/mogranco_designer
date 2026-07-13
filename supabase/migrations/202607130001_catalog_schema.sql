-- Mogranco catalog foundation for the Supabase-backed POC.
-- CSV remains the working source of truth until the importer is introduced.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text,
  sku text unique,
  vendor_name text,
  vendor_sku text,
  brand text,
  category text,
  price_cents integer check (price_cents is null or price_cents >= 0),
  cost_cents integer check (cost_cents is null or cost_cents >= 0),
  currency text not null default 'USD',
  width_in numeric,
  depth_in numeric,
  height_in numeric,
  diameter_in numeric,
  color text,
  material text,
  finish text,
  room_tags text[] not null default '{}',
  style_tags text[] not null default '{}',
  product_tags text[] not null default '{}',
  general_tags text[] not null default '{}',
  active boolean not null default true,
  source text not null default 'csv',
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (vendor_name, vendor_sku)
);

create index if not exists ix_products_active on public.products (active);
create index if not exists ix_products_category on public.products (category);
create index if not exists ix_products_name on public.products (name);
create index if not exists ix_products_vendor_name on public.products (vendor_name);
create index if not exists ix_products_vendor_sku on public.products (vendor_sku);
create index if not exists ix_products_room_tags on public.products using gin (room_tags);
create index if not exists ix_products_style_tags on public.products using gin (style_tags);
create index if not exists ix_products_product_tags on public.products using gin (product_tags);
create index if not exists ix_products_general_tags on public.products using gin (general_tags);

drop trigger if exists trg_products_set_updated_at on public.products;
create trigger trg_products_set_updated_at
before update on public.products
for each row
execute function public.set_updated_at();

create table if not exists public.product_images (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products(id) on delete cascade,
  sku text not null,
  frame_number integer not null check (frame_number >= 0),
  sort_order integer not null check (sort_order >= 0),
  storage_bucket text not null default 'product-images',
  storage_path text not null,
  public_url text,
  original_filename text not null,
  content_type text,
  size_bytes bigint check (size_bytes is null or size_bytes >= 0),
  is_primary boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (product_id, frame_number),
  unique (storage_bucket, storage_path)
);

create unique index if not exists ux_product_images_primary
  on public.product_images (product_id)
  where is_primary;

create index if not exists ix_product_images_product_sort
  on public.product_images (product_id, sort_order);

create index if not exists ix_product_images_sku
  on public.product_images (lower(sku));

drop trigger if exists trg_product_images_set_updated_at on public.product_images;
create trigger trg_product_images_set_updated_at
before update on public.product_images
for each row
execute function public.set_updated_at();

alter table public.products enable row level security;
alter table public.product_images enable row level security;

drop policy if exists "Public can read active products" on public.products;
create policy "Public can read active products"
on public.products
for select
to anon, authenticated
using (active = true);

drop policy if exists "Public can read images for active products" on public.product_images;
create policy "Public can read images for active products"
on public.product_images
for select
to anon, authenticated
using (
  exists (
    select 1
    from public.products
    where products.id = product_images.product_id
      and products.active = true
  )
);

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'product-images',
  'product-images',
  true,
  10485760,
  array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Public can read product image objects" on storage.objects;
create policy "Public can read product image objects"
on storage.objects
for select
to anon, authenticated
using (bucket_id = 'product-images');
