import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer as createViteServer, loadEnv } from "vite";
import { ImageProviderError, redesignRoom } from "./server/imageProvider.mjs";
import { InvalidUploadError } from "./server/imageNormalizer.mjs";
import {
  CatalogRequestError,
  findSelectedProducts,
  loadProductReferences,
} from "./server/catalogService.mjs";

const appDirectory = path.dirname(fileURLToPath(import.meta.url));
const env = loadEnv(process.env.NODE_ENV ?? "development", path.resolve(appDirectory, ".."), "");
const port = Number(process.env.PORT ?? env.PORT ?? 5173);
const maxUploadBytes = 15 * 1024 * 1024;
const acceptedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);

function json(response, status, body) {
  response.writeHead(status, { "Content-Type": "application/json" });
  response.end(JSON.stringify(body));
}

async function readBody(request) {
  const chunks = [];
  let size = 0;

  for await (const chunk of request) {
    size += chunk.length;
    if (size > maxUploadBytes) {
      throw new Error("UPLOAD_TOO_LARGE");
    }
    chunks.push(chunk);
  }

  return Buffer.concat(chunks);
}

const vite = await createViteServer({
  root: appDirectory,
  server: { middlewareMode: true },
  appType: "spa",
});

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);

  if (request.method === "POST" && url.pathname === "/api/redesign") {
    try {
      const contentType = (request.headers["content-type"] ?? "").split(";")[0];
      if (!acceptedTypes.has(contentType)) {
        return json(response, 415, { error: "Please upload a JPG, PNG, or WEBP image." });
      }

      const image = await readBody(request);
      if (image.length === 0) {
        return json(response, 400, { error: "Please select a room image." });
      }

      let selectedIds;
      try {
        selectedIds = JSON.parse(
          decodeURIComponent(String(request.headers["x-product-ids"] ?? "[]")),
        );
      } catch {
        throw new CatalogRequestError("The product selection is invalid.");
      }
      const selectedProducts = await findSelectedProducts(selectedIds, env);
      const referenceImages = await loadProductReferences(selectedProducts, env);

      const result = await redesignRoom({
        image,
        mimeType: contentType,
        fileName: decodeURIComponent(String(request.headers["x-file-name"] ?? "room-image")),
        instructions: decodeURIComponent(String(request.headers["x-design-instructions"] ?? "")),
        apiKey: env.OPENAI_API_KEY,
        referenceImages,
      });
      return json(response, 200, result);
    } catch (error) {
      if (error instanceof Error && error.message === "UPLOAD_TOO_LARGE") {
        return json(response, 413, { error: "The image must be smaller than 15 MB." });
      }
      if (error instanceof InvalidUploadError) {
        console.warn("Room upload rejected:", { reason: error.message });
        return json(response, 400, {
          error: "That file could not be read as a valid JPG, PNG, or WEBP image.",
        });
      }
      if (error instanceof CatalogRequestError) {
        console.warn("Product selection request failed:", {
          status: error.status,
          reason: error.message,
        });
        return json(response, error.status, { error: error.message });
      }
      if (error instanceof ImageProviderError) {
        console.error("Room redesign provider failure:", {
          message: error.message,
          requestId: error.requestId ?? null,
        });
        return json(response, 502, {
          error: "The room could not be redesigned right now. Please try again.",
        });
      }
      console.error("Unexpected room redesign failure:", {
        message: error instanceof Error ? error.message : String(error),
      });
      return json(response, 500, { error: "The room could not be redesigned right now." });
    }
  }

  vite.middlewares(request, response, () => {
    json(response, 404, { error: "Not found." });
  });
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Mogranco Designer: http://localhost:${port}`);
  console.log(env.OPENAI_API_KEY ? "Image provider: OpenAI (real)" : "Image provider: mock");
});
