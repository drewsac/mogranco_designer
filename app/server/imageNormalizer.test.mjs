import assert from "node:assert/strict";
import test from "node:test";
import sharp from "sharp";
import { InvalidUploadError, normalizeUpload } from "./imageNormalizer.mjs";

async function pixels(width = 8, height = 6, channels = 3) {
  return sharp({
    create: {
      width,
      height,
      channels,
      background: channels === 4 ? { r: 80, g: 120, b: 160, alpha: 0.5 } : "#5078a0",
    },
  });
}

async function expectSafePng(source, mimeType, fileName) {
  const normalized = await normalizeUpload({ image: source, mimeType, fileName });
  const metadata = await sharp(normalized.image).metadata();

  assert.equal(normalized.mimeType, "image/png");
  assert.equal(normalized.fileName, "room-upload.png");
  assert.equal(metadata.format, "png");
  assert.equal(metadata.space, "srgb");
  assert.ok(metadata.channels === 3 || metadata.channels === 4);
  assert.equal(metadata.orientation, undefined);
  return metadata;
}

test("normalizes an RGB JPEG", async () => {
  const source = await (await pixels()).jpeg().toBuffer();
  await expectSafePng(source, "image/jpeg", "room.jpg");
});

test("normalizes and flattens an alpha PNG", async () => {
  const source = await (await pixels(8, 6, 4)).png().toBuffer();
  const output = await expectSafePng(source, "image/png", "room.png");
  assert.equal(output.channels, 3);
});

test("normalizes a WEBP", async () => {
  const source = await (await pixels()).webp().toBuffer();
  await expectSafePng(source, "image/webp", "room.webp");
});

test("applies JPEG EXIF rotation", async () => {
  const source = await (await pixels(8, 6)).withMetadata({ orientation: 6 }).jpeg().toBuffer();
  const output = await expectSafePng(source, "image/jpeg", "rotated.jpeg");
  assert.equal(output.width, 6);
  assert.equal(output.height, 8);
});

test("converts a CMYK JPEG to sRGB", async () => {
  const source = await (await pixels()).toColourspace("cmyk").jpeg().toBuffer();
  const sourceMetadata = await sharp(source).metadata();
  assert.equal(sourceMetadata.space, "cmyk");
  await expectSafePng(source, "image/jpeg", "cmyk.jpg");
});

test("rejects fake image bytes with a supported name and MIME type", async () => {
  await assert.rejects(
    normalizeUpload({
      image: Buffer.from("this is not an image"),
      mimeType: "image/jpeg",
      fileName: "fake.jpg",
    }),
    InvalidUploadError,
  );
});

test("rejects metadata that disagrees with decoded bytes", async () => {
  const source = await (await pixels()).png().toBuffer();
  await assert.rejects(
    normalizeUpload({ image: source, mimeType: "image/jpeg", fileName: "room.jpg" }),
    InvalidUploadError,
  );
});
