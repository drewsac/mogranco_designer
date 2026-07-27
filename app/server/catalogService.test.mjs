import assert from "node:assert/strict";
import test from "node:test";
import {
  CatalogRequestError,
  findSelectedProducts,
  loadProductReferences,
} from "./catalogService.mjs";

const oneSku = ["mg-p520-016-rc"];
const tenSkus = [
  "mg-p520-016-rc",
  "mg-av-1247",
  "mg-av-1348ardp",
  "mg-av-1633rdp",
  "mg-av-1738wd",
  "mg-av-1772",
  "mg-av-1827rdp",
  "mg-av-1865",
  "mg-av-1922",
  "mg-av-1927",
];

test("resolves one stable product identifier from the catalog fallback", async () => {
  const products = await findSelectedProducts(oneSku, {});
  assert.equal(products.length, 1);
  assert.equal(products[0].sku, oneSku[0]);
  assert.equal(products[0].widthIn, 32);
  assert.equal(products[0].depthIn, 40);
  assert.equal(products[0].heightIn, 34);
});

test("resolves ten ordered stable product identifiers", async () => {
  const products = await findSelectedProducts(tenSkus, {});
  assert.deepEqual(
    products.map((product) => product.sku),
    tenSkus,
  );
  const references = await loadProductReferences(products, {});
  assert.equal(references.length, 10);
  assert.ok(references.every((reference) => reference.mimeType === "image/png"));
});

test("rejects an eleventh product", async () => {
  await assert.rejects(
    findSelectedProducts([...tenSkus, "mg-av-1931"], {}),
    CatalogRequestError,
  );
});

test("rejects duplicate product identifiers", async () => {
  await assert.rejects(
    findSelectedProducts([oneSku[0], oneSku[0]], {}),
    CatalogRequestError,
  );
});

test("rejects an unknown product identifier", async () => {
  await assert.rejects(findSelectedProducts(["mg-does-not-exist"], {}), CatalogRequestError);
});

test("fails cleanly when a selected product image is inaccessible", async () => {
  await assert.rejects(
    loadProductReferences(
      [
        {
          id: "missing-image",
          sku: "missing-image",
          name: "Missing image fixture",
          imageUrl: "/product-images/does-not-exist.jpg",
          source: "local",
        },
      ],
      {},
    ),
    CatalogRequestError,
  );
});
