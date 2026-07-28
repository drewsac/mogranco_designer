import assert from "node:assert/strict";
import test from "node:test";
import { buildPrompt } from "./imageProvider.mjs";

test("includes available product dimensions in the image prompt", () => {
  const prompt = buildPrompt("", [
    {
      name: "Alba swivel chair",
      sku: "mg-alba-016-rc",
      widthIn: 28,
      depthIn: "32",
      heightIn: 35,
      diameterIn: null,
    },
  ]);

  assert.match(
    prompt,
    /Real-world dimensions: 28 in W × 32 in D × 35 in H\./,
  );
  assert.match(prompt, /render each product at physically accurate scale/);
});

test("omits the dimensions sentence when measurements are unavailable", () => {
  const prompt = buildPrompt("", [
    {
      name: "Product without measurements",
      sku: "mg-no-dimensions",
      widthIn: null,
      depthIn: "",
      heightIn: 0,
      diameterIn: null,
    },
  ]);

  assert.doesNotMatch(prompt, /Real-world dimensions:/);
});
