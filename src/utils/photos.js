import fs from 'node:fs';
import path from 'node:path';
import photosMapping from './photos_mapping.json';

const PROCESSED_PHOTOS_DIR = path.resolve(process.cwd(), 'processed_photos');
const photoDateCache = new Map();

/**
 * Extracts date from a photo file (from EXIF header, falling back to mtime).
 *
 * @param {string} photoNameOrPath
 * @returns {Date | null}
 */
export function getPhotoDate(photoNameOrPath) {
  if (!photoNameOrPath || typeof photoNameOrPath !== 'string') return null;

  const fileName = path.basename(photoNameOrPath.trim());
  if (!fileName) return null;

  if (photoDateCache.has(fileName)) {
    return photoDateCache.get(fileName);
  }

  const fullPath = path.isAbsolute(photoNameOrPath) && fs.existsSync(photoNameOrPath)
    ? photoNameOrPath
    : path.join(PROCESSED_PHOTOS_DIR, fileName);

  if (!fs.existsSync(fullPath)) {
    photoDateCache.set(fileName, null);
    return null;
  }

  try {
    const fd = fs.openSync(fullPath, 'r');
    const buf = Buffer.alloc(100000);
    const bytesRead = fs.readSync(fd, buf, 0, 100000, 0);
    fs.closeSync(fd);

    const str = buf.toString('latin1', 0, bytesRead);
    // Find EXIF date in format: YYYY:MM:DD HH:MM:SS
    const match = str.match(/(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})/);
    if (match) {
      const [, y, m, d, hh, mm, ss] = match;
      const iso = `${y}-${m}-${d}T${hh}:${mm}:${ss}Z`;
      const date = new Date(iso);
      if (Number.isFinite(date.getTime())) {
        photoDateCache.set(fileName, date);
        return date;
      }
    }

    const stat = fs.statSync(fullPath);
    const date = stat.mtime;
    photoDateCache.set(fileName, date);
    return date;
  } catch {
    photoDateCache.set(fileName, null);
    return null;
  }
}

/**
 * Resolves the original photo date for a given book entry or book object.
 * Checks in order:
 * 1. book.data?.photoDate or book.photoDate
 * 2. photo file in book.data?.photo or book.photo
 * 3. mapped photo file from photosMapping[book.id]
 *
 * @param {{ id?: string; data?: { photo?: string; photoDate?: Date | string; addedAt?: Date | string }; photo?: string; photoDate?: Date | string }} book
 * @returns {Date | null}
 */
export function getBookPhotoDate(book) {
  if (!book) return null;

  // 1. Explicit photoDate
  const explicitPhotoDate = book.data?.photoDate ?? book.photoDate;
  if (explicitPhotoDate) {
    const d = explicitPhotoDate instanceof Date ? explicitPhotoDate : new Date(explicitPhotoDate);
    if (Number.isFinite(d.getTime())) return d;
  }

  // 2. Explicit photo property
  const explicitPhoto = book.data?.photo ?? book.photo;
  if (explicitPhoto) {
    const date = getPhotoDate(explicitPhoto);
    if (date) return date;
  }

  // 3. Mapped photo by book.id / slug
  const bookId = book.id ? String(book.id).replace(/\.md$/, '') : '';
  if (bookId && photosMapping[bookId]) {
    const date = getPhotoDate(photosMapping[bookId]);
    if (date) return date;
  }

  return null;
}
