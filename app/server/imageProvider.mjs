const DESIGN_PROMPT = `Redesign this photographed room in the Modern Grace & Co. aesthetic: sophisticated, warm, high-end, layered, and curated; contemporary with transitional influence; a neutral palette with restrained contrast; natural materials; and the polish of an upscale residential interior-design boutique. Update furnishings, lighting, decor, finishes, color palette, and styling while maintaining a believable, photorealistic interior.`;

const PRESERVATION_PROMPT = `Preserve the original room's architecture, spatial layout, proportions, and exact camera viewpoint as closely as possible. Do not add, remove, relocate, resize, or reshape doors, windows, walls, fireplaces, built-ins, ceiling features, stairs, or other major architectural elements. Keep the room recognizably the same physical space.`;

function buildPrompt(instructions, products) {
  const userRequest = instructions.trim()
    ? `The client's requested changes are: ${instructions.trim()}`
    : "The client provided no additional change request; use your best design judgment.";
  const productRoles = products
    .map(
      (product, index) =>
        `Image ${index + 2} is the exact Mogranco product "${product.name}" (SKU: ${product.sku || "not assigned"}).`,
    )
    .join("\n");
  return `${DESIGN_PROMPT}

Image 1 is the room to redesign. It must determine the architecture, viewpoint, scale, floor plan, and overall scene.
${productRoles}

Treat Images 2 onward as an approved set of exact Mogranco products available for this room. Select and visibly incorporate the products that genuinely suit the room, composition, scale, and design; you do not need to use every referenced product. For every product you do use, preserve its recognizable silhouette, material, finish, color, pattern, and distinguishing design features as closely as possible, and place it at plausible scale and perspective. Do not use the references merely as general style inspiration, and do not invent substitutions for the referenced products.

${userRequest}

${PRESERVATION_PROMPT}`;
}

function dataUrl(image, mimeType) {
  return `data:${mimeType};base64,${image.toString("base64")}`;
}

export class ImageProviderError extends Error {
  constructor(message, requestId) {
    super(message);
    this.name = "ImageProviderError";
    this.requestId = requestId;
  }
}

export async function redesignRoom({
  image,
  mimeType,
  fileName,
  instructions,
  apiKey,
  referenceImages,
}) {
  const normalized = await normalizeUpload({ image, mimeType, fileName });
  console.info("Room upload normalized:", normalized.diagnostic);

  if (!apiKey) {
    return {
      imageUrl: dataUrl(normalized.image, normalized.mimeType),
      mock: true,
      message:
        "Mock mode is active. Product placement was not generated; add OPENAI_API_KEY for a real redesign.",
    };
  }

  const body = new FormData();
  body.append("model", "gpt-image-2");
  body.append(
    "image[]",
    new Blob([normalized.image], { type: normalized.mimeType }),
    "room-upload.png",
  );
  referenceImages.forEach((reference, index) => {
    body.append(
      "image[]",
      new Blob([reference.image], { type: "image/png" }),
      `product-${index + 1}.png`,
    );
  });
  body.append("prompt", buildPrompt(instructions, referenceImages.map(({ product }) => product)));
  body.append("quality", "medium");
  console.info("OpenAI image edit request prepared:", {
    imageOrder: [
      { image: 1, role: "room" },
      ...referenceImages.map(({ product }, index) => ({
        image: index + 2,
        role: "product",
        id: product.id,
        sku: product.sku,
        name: product.name,
      })),
    ],
  });

  const response = await fetch("https://api.openai.com/v1/images/edits", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}` },
    body,
  });
  const requestId = response.headers.get("x-request-id");
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    console.error("OpenAI image edit failed:", {
      status: response.status,
      requestId,
      code: payload?.error?.code ?? null,
      type: payload?.error?.type ?? null,
      message: payload?.error?.message ?? "No error message returned",
    });
    throw new ImageProviderError("OpenAI image edit failed", requestId);
  }

  const encodedImage = payload?.data?.[0]?.b64_json;
  if (!encodedImage) {
    console.error("OpenAI image edit returned no image:", { requestId });
    throw new ImageProviderError("OpenAI returned no image", requestId);
  }

  console.info("OpenAI image edit succeeded:", {
    requestId,
    products: referenceImages.map(({ product }) => ({
      id: product.id,
      sku: product.sku,
      name: product.name,
    })),
  });
  return { imageUrl: `data:image/png;base64,${encodedImage}`, mock: false };
}
import { normalizeUpload } from "./imageNormalizer.mjs";
