import path from "node:path";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createClient } from "@supabase/supabase-js";
import { InvalidUploadError, normalizeUpload } from "./imageNormalizer.mjs";

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const skuPattern = /^[a-z0-9][a-z0-9._-]{0,127}$/i;
const imageTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const maxProductImageBytes = 10 * 1024 * 1024;
const appDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const staticCatalogPath = path.join(appDirectory, "public", "data", "products.json");
const staticImageDirectory = path.join(appDirectory, "public", "product-images");

export class CatalogRequestError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.name = "CatalogRequestError";
    this.status = status;
  }
}

function primaryImage(images = []) {
  return (
    images.find((image) => image.is_primary) ??
    [...images].sort((a, b) => a.sort_order - b.sort_order)[0] ??
    null
  );
}

export async function findSelectedProducts(ids, env) {
  if (!Array.isArray(ids) || ids.length < 1 || ids.length > 10) {
    throw new CatalogRequestError("Select between one and ten products.");
  }
  if (new Set(ids).size !== ids.length) {
    throw new CatalogRequestError("Duplicate product selections are not allowed.");
  }
  if (
    ids.some(
      (id) => typeof id !== "string" || (!uuidPattern.test(id) && !skuPattern.test(id)),
    )
  ) {
    throw new CatalogRequestError("One or more product selections are invalid.");
  }

  const supabaseUrl = env.VITE_SUPABASE_URL ?? env.SUPABASE_URL;
  const supabaseKey = env.VITE_SUPABASE_PUBLISHABLE_KEY ?? env.VITE_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !supabaseKey) {
    return findStaticProducts(ids);
  }

  const supabase = createClient(supabaseUrl, supabaseKey);
  const identifierColumn = ids.every((id) => uuidPattern.test(id)) ? "id" : "sku";
  const { data, error } = await supabase
    .from("products")
    .select(`
      id,
      name,
      sku,
      category,
      price_cents,
      width_in,
      depth_in,
      height_in,
      diameter_in,
      active,
      product_images (
        public_url,
        storage_bucket,
        storage_path,
        is_primary,
        sort_order
      )
    `)
    .in(identifierColumn, ids)
    .eq("active", true);

  if (error) {
    console.warn("Supabase product lookup failed; using the existing static catalog:", {
      code: error.code ?? null,
      message: error.message,
    });
    return findStaticProducts(ids);
  }
  if (!data || data.length !== ids.length) {
    throw new CatalogRequestError("One or more selected products were not found.");
  }

  const byId = new Map(data.map((product) => [product[identifierColumn], product]));
  return ids.map((id) => {
    const product = byId.get(id);
    const image = primaryImage(product.product_images);
    if (!image?.public_url) {
      throw new CatalogRequestError(`${product.name} does not have an available product image.`);
    }
    return {
      id: product.id,
      name: product.name,
      sku: product.sku ?? "",
      category: product.category ?? "",
      price: product.price_cents === null ? null : product.price_cents / 100,
      widthIn: product.width_in ?? null,
      depthIn: product.depth_in ?? null,
      heightIn: product.height_in ?? null,
      diameterIn: product.diameter_in ?? null,
      imageUrl: image.public_url,
      storageBucket: image.storage_bucket,
      source: "supabase",
    };
  });
}

async function findStaticProducts(ids) {
  let catalog;
  try {
    catalog = JSON.parse(await readFile(staticCatalogPath, "utf8"));
  } catch (error) {
    console.error("Static product catalog could not be loaded:", {
      message: error instanceof Error ? error.message : String(error),
    });
    throw new CatalogRequestError("The selected products could not be loaded.", 503);
  }

  const byId = new Map(
    catalog
      .filter((product) => product.active)
      .map((product) => [product.id || product.sku, product]),
  );
  return ids.map((id) => {
    const product = byId.get(id);
    if (!product) {
      throw new CatalogRequestError("One or more selected products were not found.");
    }
    if (!product.image_src) {
      throw new CatalogRequestError(`${product.name} does not have an available product image.`);
    }
    return {
      id,
      name: product.name,
      sku: product.sku ?? "",
      category: product.category ?? "",
      price: product.price ?? null,
      widthIn: product.width_in ?? null,
      depthIn: product.depth_in ?? null,
      heightIn: product.height_in ?? null,
      diameterIn: product.diameter_in ?? null,
      imageUrl: product.image_src,
      source: "local",
    };
  });
}

function assertTrustedProductUrl(product, supabaseUrl) {
  let imageUrl;
  let projectUrl;
  try {
    imageUrl = new URL(product.imageUrl);
    projectUrl = new URL(supabaseUrl);
  } catch {
    throw new CatalogRequestError(`${product.name} has an invalid product image URL.`, 502);
  }

  const trustedPrefix = `/storage/v1/object/public/${encodeURIComponent(product.storageBucket)}/`;
  if (
    imageUrl.origin !== projectUrl.origin ||
    product.storageBucket !== "product-images" ||
    !imageUrl.pathname.startsWith(trustedPrefix)
  ) {
    throw new CatalogRequestError(`${product.name} has an untrusted product image URL.`, 502);
  }
  return imageUrl;
}

async function readLimitedResponse(response, productName) {
  const declaredLength = Number(response.headers.get("content-length") ?? 0);
  if (declaredLength > maxProductImageBytes) {
    throw new CatalogRequestError(`${productName}'s image is too large.`, 502);
  }

  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length > maxProductImageBytes) {
    throw new CatalogRequestError(`${productName}'s image is too large.`, 502);
  }
  return bytes;
}

export async function loadProductReferences(products, env) {
  const supabaseUrl = env.VITE_SUPABASE_URL ?? env.SUPABASE_URL;

  return Promise.all(
    products.map(async (product) => {
      if (product.source === "local") {
        const fileName = path.basename(product.imageUrl);
        const imagePath = path.resolve(staticImageDirectory, fileName);
        if (!imagePath.startsWith(`${staticImageDirectory}${path.sep}`)) {
          throw new CatalogRequestError(`${product.name} has an invalid product image path.`, 502);
        }
        let image;
        try {
          image = await readFile(imagePath);
        } catch (error) {
          console.error("Local product image could not be loaded:", {
            productId: product.id,
            sku: product.sku,
            message: error instanceof Error ? error.message : String(error),
          });
          throw new CatalogRequestError(`${product.name}'s image could not be loaded.`, 502);
        }
        if (image.length > maxProductImageBytes) {
          throw new CatalogRequestError(`${product.name}'s image is too large.`, 502);
        }
        return normalizeProductImage(product, image, fileName, mimeTypeForFile(fileName));
      }

      const imageUrl = assertTrustedProductUrl(product, supabaseUrl);
      let response;
      try {
        response = await fetch(imageUrl, { redirect: "error" });
      } catch (error) {
        console.error("Product image download failed:", {
          productId: product.id,
          sku: product.sku,
          message: error instanceof Error ? error.message : String(error),
        });
        throw new CatalogRequestError(`${product.name}'s image could not be loaded.`, 502);
      }
      if (!response.ok) {
        console.error("Product image download returned an error:", {
          productId: product.id,
          sku: product.sku,
          status: response.status,
        });
        throw new CatalogRequestError(`${product.name}'s image could not be loaded.`, 502);
      }

      const mimeType = (response.headers.get("content-type") ?? "").split(";")[0];
      if (!imageTypes.has(mimeType)) {
        throw new CatalogRequestError(`${product.name}'s image format is not supported.`, 502);
      }

      const image = await readLimitedResponse(response, product.name);
      return normalizeProductImage(
        product,
        image,
        path.basename(decodeURIComponent(imageUrl.pathname)),
        mimeType,
      );
    }),
  );
}

function mimeTypeForFile(fileName) {
  const extension = path.extname(fileName).toLowerCase();
  return extension === ".png"
    ? "image/png"
    : extension === ".webp"
      ? "image/webp"
      : "image/jpeg";
}

async function normalizeProductImage(product, image, fileName, mimeType) {
  let normalized;
  try {
    normalized = await normalizeUpload({ image, mimeType, fileName });
  } catch (error) {
    if (error instanceof InvalidUploadError) {
      console.error("Product image decode failed:", {
        productId: product.id,
        sku: product.sku,
        reason: error.message,
      });
      throw new CatalogRequestError(`${product.name}'s image could not be decoded.`, 502);
    }
    throw error;
  }
  console.info("Product reference normalized:", {
    productId: product.id,
    sku: product.sku,
    ...normalized.diagnostic,
  });
  return { ...normalized, product };
}
