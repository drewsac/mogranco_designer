import path from "node:path";
import sharp from "sharp";

const formatDetails = {
  jpeg: { mimeType: "image/jpeg", extensions: new Set([".jpg", ".jpeg"]) },
  png: { mimeType: "image/png", extensions: new Set([".png"]) },
  webp: { mimeType: "image/webp", extensions: new Set([".webp"]) },
};

export class InvalidUploadError extends Error {
  constructor(diagnosticMessage) {
    super(diagnosticMessage);
    this.name = "InvalidUploadError";
  }
}

export async function normalizeUpload({ image, mimeType, fileName }) {
  const safeFileName = path.basename(fileName);
  const extension = path.extname(safeFileName).toLowerCase();

  try {
    const source = sharp(image, {
      failOn: "error",
      limitInputPixels: 40_000_000,
      sequentialRead: true,
    });
    const metadata = await source.metadata();
    const details = formatDetails[metadata.format];

    if (!details) {
      throw new InvalidUploadError(`Decoded unsupported image format: ${metadata.format ?? "unknown"}`);
    }
    if (details.mimeType !== mimeType) {
      throw new InvalidUploadError(
        `MIME mismatch: reported ${mimeType}, decoded ${details.mimeType}`,
      );
    }
    if (!details.extensions.has(extension)) {
      throw new InvalidUploadError(
        `Extension mismatch: ${extension || "(none)"} does not match ${metadata.format}`,
      );
    }

    const { data, info } = await source
      .rotate()
      .flatten({ background: "#ffffff" })
      .toColourspace("srgb")
      .png({ compressionLevel: 9 })
      .toBuffer({ resolveWithObject: true });

    if (info.format !== "png" || ![3, 4].includes(info.channels)) {
      throw new InvalidUploadError(
        `Unsafe normalized output: ${info.format}, ${info.channels} channels`,
      );
    }

    return {
      image: data,
      mimeType: "image/png",
      fileName: "room-upload.png",
      diagnostic: {
        sourceFileName: safeFileName,
        sourceFormat: metadata.format,
        sourceMimeType: mimeType,
        sourceBytes: image.length,
        sourceWidth: metadata.width,
        sourceHeight: metadata.height,
        sourceSpace: metadata.space,
        sourceChannels: metadata.channels,
        sourceOrientation: metadata.orientation ?? null,
        normalizedBytes: data.length,
        normalizedWidth: info.width,
        normalizedHeight: info.height,
        normalizedSpace: "srgb",
        normalizedChannels: info.channels,
      },
    };
  } catch (error) {
    if (error instanceof InvalidUploadError) {
      throw error;
    }
    throw new InvalidUploadError(
      error instanceof Error ? `Image decode failed: ${error.message}` : "Image decode failed",
    );
  }
}
