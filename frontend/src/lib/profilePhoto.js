export const PHOTO_MAX_BYTES = 5 * 1024 * 1024;
export const PHOTO_ACCEPT = "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp";
export const PHOTO_OUTPUT_SIZE = 512;
export const PHOTO_FILL = "#0B2E59";
export const PHOTO_INVALID = "Please choose a JPG, PNG, or WebP image up to 5 MB.";

const ALLOWED_TYPES = new Set(["image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/webp"]);
const ALLOWED_EXT = /\.(jpe?g|png|webp)$/i;

export function validatePhotoFile(file) {
  if (!file || typeof file.size !== "number" || file.size <= 0 || file.size > PHOTO_MAX_BYTES) {
    return PHOTO_INVALID;
  }
  const type = String(file.type || "").toLowerCase();
  const name = String(file.name || "");
  if (ALLOWED_TYPES.has(type)) return "";
  if ((!type || type === "application/octet-stream") && ALLOWED_EXT.test(name)) return "";
  return PHOTO_INVALID;
}

export function coverVisible(width, height, zoom) {
  const minSide = Math.min(width, height);
  return minSide / Math.max(1, zoom);
}

export function clampPan(sx, sy, width, height, zoom) {
  const visible = coverVisible(width, height, zoom);
  return {
    sx: Math.min(Math.max(0, sx), Math.max(0, width - visible)),
    sy: Math.min(Math.max(0, sy), Math.max(0, height - visible)),
  };
}

export function initialCrop(width, height) {
  const visible = coverVisible(width, height, 1);
  return {
    zoom: 1,
    sx: (width - visible) / 2,
    sy: (height - visible) / 2,
  };
}

export function maxZoomFor(width, height) {
  const minSide = Math.min(width, height);
  return Math.max(1.5, Math.min(4, minSide / 96));
}

export function cropImageStyle(width, height, crop, cropSize) {
  const visible = coverVisible(width, height, crop.zoom);
  const scale = cropSize / visible;
  return {
    width: `${width * scale}px`,
    height: `${height * scale}px`,
    transform: `translate(${-crop.sx * scale}px, ${-crop.sy * scale}px)`,
  };
}

function jpegOrientation(buffer) {
  const view = new DataView(buffer);
  if (view.byteLength < 4 || view.getUint16(0, false) !== 0xffd8) return 1;
  let offset = 2;
  while (offset + 4 < view.byteLength) {
    const marker = view.getUint16(offset, false);
    offset += 2;
    if ((marker & 0xff00) !== 0xff00) break;
    if (marker === 0xffda) break;
    const size = view.getUint16(offset, false);
    if (marker === 0xffe1 && offset + size <= view.byteLength && size >= 8) {
      if (view.getUint32(offset + 2, false) === 0x45786966 && view.getUint16(offset + 6, false) === 0) {
        const tiff = offset + 8;
        const little = view.getUint16(tiff, false) === 0x4949;
        if (view.getUint16(tiff, little) !== 0x002a) return 1;
        const dir = tiff + view.getUint32(tiff + 4, little);
        if (dir + 2 > view.byteLength) return 1;
        const count = view.getUint16(dir, little);
        for (let i = 0; i < count; i += 1) {
          const entry = dir + 2 + i * 12;
          if (entry + 10 > view.byteLength) break;
          if (view.getUint16(entry, little) === 0x0112) {
            return view.getUint16(entry + 8, little) || 1;
          }
        }
      }
      return 1;
    }
    offset += size;
  }
  return 1;
}

function applyOrientation(ctx, orientation, width, height) {
  switch (orientation) {
    case 2:
      ctx.translate(width, 0);
      ctx.scale(-1, 1);
      break;
    case 3:
      ctx.translate(width, height);
      ctx.rotate(Math.PI);
      break;
    case 4:
      ctx.translate(0, height);
      ctx.scale(1, -1);
      break;
    case 5:
      ctx.rotate(0.5 * Math.PI);
      ctx.scale(1, -1);
      break;
    case 6:
      ctx.rotate(0.5 * Math.PI);
      ctx.translate(0, -height);
      break;
    case 7:
      ctx.rotate(0.5 * Math.PI);
      ctx.translate(width, -height);
      ctx.scale(-1, 1);
      break;
    case 8:
      ctx.rotate(-0.5 * Math.PI);
      ctx.translate(-width, 0);
      break;
    default:
      break;
  }
}

function loadHtmlImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("We couldn't read this image. Please choose another photo."));
    image.src = src;
  });
}

async function loadWithExifFallback(file) {
  const buffer = await file.arrayBuffer();
  const orientation = jpegOrientation(buffer);
  const blob = new Blob([buffer], { type: file.type || "image/jpeg" });
  const url = URL.createObjectURL(blob);
  try {
    const image = await loadHtmlImage(url);
    const width = image.naturalWidth || image.width;
    const height = image.naturalHeight || image.height;
    if (!width || !height) throw new Error("We couldn't read this image. Please choose another photo.");
    if (orientation === 1) return { source: image, width, height };
    const swapped = orientation >= 5;
    const canvas = document.createElement("canvas");
    canvas.width = swapped ? height : width;
    canvas.height = swapped ? width : height;
    const ctx = canvas.getContext("2d");
    applyOrientation(ctx, orientation, width, height);
    ctx.drawImage(image, 0, 0);
    return { source: canvas, width: canvas.width, height: canvas.height };
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function loadOrientedImage(file) {
  if (typeof createImageBitmap === "function") {
    try {
      const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
      return { source: bitmap, width: bitmap.width, height: bitmap.height };
    } catch {
      try {
        const bitmap = await createImageBitmap(file);
        return { source: bitmap, width: bitmap.width, height: bitmap.height };
      } catch {
        /* use EXIF fallback */
      }
    }
  }
  return loadWithExifFallback(file);
}

export const COVER_ASPECT = 16 / 5;
export const COVER_OUTPUT_WIDTH = 1600;
export const COVER_OUTPUT_HEIGHT = 500;

export function coverFrame(width, height, zoom, aspect = COVER_ASPECT) {
  const safeZoom = Math.max(1, zoom || 1);
  const imageAspect = width / Math.max(1, height);
  const baseW = imageAspect > aspect ? height * aspect : width;
  const baseH = imageAspect > aspect ? height : width / aspect;
  return {
    visibleW: baseW / safeZoom,
    visibleH: baseH / safeZoom,
  };
}

export function clampPanFrame(sx, sy, width, height, zoom, aspect = COVER_ASPECT) {
  const { visibleW, visibleH } = coverFrame(width, height, zoom, aspect);
  return {
    sx: Math.min(Math.max(0, sx), Math.max(0, width - visibleW)),
    sy: Math.min(Math.max(0, sy), Math.max(0, height - visibleH)),
  };
}

export function initialCropFrame(width, height, aspect = COVER_ASPECT) {
  const { visibleW, visibleH } = coverFrame(width, height, 1, aspect);
  return {
    zoom: 1,
    sx: (width - visibleW) / 2,
    sy: (height - visibleH) / 2,
  };
}

export function maxZoomForFrame(width, height, aspect = COVER_ASPECT) {
  const { visibleW, visibleH } = coverFrame(width, height, 1, aspect);
  const minSide = Math.min(visibleW, visibleH);
  return Math.max(1.5, Math.min(4, minSide / 80));
}

export function cropFrameStyle(width, height, crop, frameWidth, aspect = COVER_ASPECT) {
  const { visibleW } = coverFrame(width, height, crop.zoom, aspect);
  const scale = frameWidth / visibleW;
  return {
    width: `${width * scale}px`,
    height: `${height * scale}px`,
    transform: `translate(${-crop.sx * scale}px, ${-crop.sy * scale}px)`,
  };
}

export async function exportCroppedFrame(
  source,
  width,
  height,
  crop,
  outputWidth = COVER_OUTPUT_WIDTH,
  outputHeight = COVER_OUTPUT_HEIGHT,
  aspect = COVER_ASPECT,
) {
  const { visibleW, visibleH } = coverFrame(width, height, crop.zoom, aspect);
  const canvas = document.createElement("canvas");
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = PHOTO_FILL;
  ctx.fillRect(0, 0, outputWidth, outputHeight);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, crop.sx, crop.sy, visibleW, visibleH, 0, 0, outputWidth, outputHeight);
  const blob = await new Promise((resolve, reject) => {
    canvas.toBlob(
      (next) => (next ? resolve(next) : reject(new Error("We couldn't update your cover photo. Please try again."))),
      "image/jpeg",
      0.92,
    );
  });
  if (blob.size > PHOTO_MAX_BYTES) {
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (next) => (next ? resolve(next) : reject(new Error("We couldn't update your cover photo. Please try again."))),
        "image/jpeg",
        0.8,
      );
    });
  }
  return blob;
}

export async function exportCroppedPhoto(source, width, height, crop, outputSize = PHOTO_OUTPUT_SIZE) {
  const visible = coverVisible(width, height, crop.zoom);
  const canvas = document.createElement("canvas");
  canvas.width = outputSize;
  canvas.height = outputSize;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = PHOTO_FILL;
  ctx.fillRect(0, 0, outputSize, outputSize);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, crop.sx, crop.sy, visible, visible, 0, 0, outputSize, outputSize);
  const blob = await new Promise((resolve, reject) => {
    canvas.toBlob(
      (next) => (next ? resolve(next) : reject(new Error("We couldn't update your profile photo. Please try again."))),
      "image/jpeg",
      0.92
    );
  });
  if (blob.size > PHOTO_MAX_BYTES) {
    const smaller = await new Promise((resolve, reject) => {
      canvas.toBlob(
        (next) => (next ? resolve(next) : reject(new Error("We couldn't update your profile photo. Please try again."))),
        "image/jpeg",
        0.8
      );
    });
    return smaller;
  }
  return blob;
}
