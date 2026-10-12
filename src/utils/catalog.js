/**
 * Normalizes text for case-insensitive and character-agnostic comparison:
 * lowercase, 'ё' -> 'е', and trimmed.
 *
 * @param {string | null | undefined} [text]
 * @returns {string}
 */
export function normalize(text) {
  return String(text ?? '').toLowerCase().replace(/ё/g, 'е').trim();
}

/**
 * Normalizes and strips prefixes/hyphens/dashes from an ISBN string.
 *
 * @param {string} [isbn]
 * @returns {string}
 */
export function cleanIsbn(isbn) {
  return normalize(isbn)
    .replace(/^isbn(?:[:\s\u2010-\u2015\u2212-]*1[03])?[:\s\u2010-\u2015\u2212-]*/i, '')
    .replace(/[-\s\u2010-\u2015\u2212]/g, '');
}

/**
 * Checks if a book matches search criteria.
 * Search supports multi-word queries across title and author, or ISBN match.
 *
 * @param {{ title?: string; author?: string; isbn?: string }} book
 * @param {string} searchQuery
 * @returns {boolean}
 */
export function matchesSearch(book, searchQuery) {
  if (!book) return false;
  if (!searchQuery) return true;
  const normalizedQuery = normalize(searchQuery);
  if (!normalizedQuery) return true;

  const title = normalize(book.title ?? '');
  const author = normalize(book.author ?? '');
  const cleanIsbnValue = cleanIsbn(book.isbn);
  const cleanQuery = cleanIsbn(normalizedQuery);
  const queryWords = normalizedQuery.split(/[\s,;:.!?«»"()[\]{}]+/).filter(Boolean);

  const matchesAllWords = queryWords.length > 0 && queryWords.every(
    (word) => title.includes(word) || author.includes(word)
  );

  const hasIsbnPrefix = /^isbn/i.test(normalizedQuery);
  const matchesIsbn = (hasIsbnPrefix || cleanQuery.length >= 4) && cleanQuery.length > 0 && cleanIsbnValue.includes(cleanQuery);

  return matchesAllWords || matchesIsbn;
}

/**
 * Checks if a book matches a selected genre.
 *
 * @param {{ genres?: string | string[] }} book
 * @param {string} selectedGenre
 * @returns {boolean}
 */
export function matchesGenre(book, selectedGenre) {
  const normalizedGenre = normalize(selectedGenre);
  if (!normalizedGenre) return true;
  if (!book) return false;

  let itemGenres = [];
  if (Array.isArray(book.genres)) {
    itemGenres = book.genres.map((g) => normalize(g));
  } else if (typeof book.genres === 'string') {
    const trimmed = book.genres.trim();
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        itemGenres = JSON.parse(trimmed).map((g) => normalize(g));
      } catch {
        itemGenres = trimmed
          .slice(1, -1)
          .split(',')
          .map((g) => normalize(g.trim().replace(/^['"]+|['"]+$/g, '')))
          .filter(Boolean);
      }
    } else {
      itemGenres = normalize(trimmed).split(',').map((g) => g.trim());
    }
  }
  return itemGenres.includes(normalizedGenre);
}

/**
 * Checks if a book matches both search query and selected genre.
 *
 * @param {{ title?: string; author?: string; isbn?: string; genres?: string | string[] }} book
 * @param {string} searchQuery
 * @param {string} selectedGenre
 * @returns {boolean}
 */
export function matchesFilter(book, searchQuery, selectedGenre) {
  if (!book) return false;
  return matchesSearch(book, searchQuery) && matchesGenre(book, selectedGenre);
}

export function parseDateValue(val) {
  if (val === null || val === undefined || val === '') return 0;
  if (val instanceof Date) {
    const t = val.getTime();
    return Number.isFinite(t) ? t : 0;
  }
  if (typeof val === 'number') {
    return Number.isFinite(val) ? val : 0;
  }
  const str = String(val).trim();
  if (!str) return 0;
  if (/^-?\d+(\.\d+)?$/.test(str)) {
    const num = Number(str);
    return Number.isFinite(num) ? num : 0;
  }
  const parsed = Date.parse(str);
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Sort comparator for catalog books.
 * Supported modes: 'recent', 'title', 'author'.
 *
 * In 'recent' mode:
 * 1. Book publication year (year descending)
 * 2. Book addition date (added / addedAt descending), or original photo date (photoDate / photo_date) if addition date is missing
 * 3. Tie-breakers: title ascending, id ascending
 *
 * @param {{ id?: string; title?: string; author?: string; added?: number | string | Date; addedAt?: number | string | Date; photoDate?: number | string | Date; photo_date?: number | string | Date; year?: number | string }} a
 * @param {{ id?: string; title?: string; author?: string; added?: number | string | Date; addedAt?: number | string | Date; photoDate?: number | string | Date; photo_date?: number | string | Date; year?: number | string }} b
 * @param {string} [sortMode='recent']
 * @returns {number}
 */
export function compareBooks(a, b, sortMode = 'recent') {
  a = a || {};
  b = b || {};

  const titleA = String(a.title ?? '').trim();
  const titleB = String(b.title ?? '').trim();
  const authorA = String(a.author ?? '').trim();
  const authorB = String(b.author ?? '').trim();
  const idA = String(a.id ?? '');
  const idB = String(b.id ?? '');

  if (sortMode === 'title') {
    const titleDiff = titleA.localeCompare(titleB, 'ru', { sensitivity: 'accent' });
    if (titleDiff !== 0) return titleDiff;
    const authorDiff = authorA.localeCompare(authorB, 'ru', { sensitivity: 'accent' });
    if (authorDiff !== 0) return authorDiff;
    return idA.localeCompare(idB);
  }

  if (sortMode === 'author') {
    if (!authorA && authorB) return 1;
    if (authorA && !authorB) return -1;
    const authorDiff = authorA.localeCompare(authorB, 'ru', { sensitivity: 'accent' });
    if (authorDiff !== 0) return authorDiff;
    const titleDiff = titleA.localeCompare(titleB, 'ru', { sensitivity: 'accent' });
    if (titleDiff !== 0) return titleDiff;
    return idA.localeCompare(idB);
  }

  // "recent" mode:
  // 1. Publication year descending (newer books first)
  const parsedYearA = typeof a.year === 'number' ? a.year : parseInt(String(a.year || 0), 10);
  const yearA = Number.isFinite(parsedYearA) ? parsedYearA : 0;
  const parsedYearB = typeof b.year === 'number' ? b.year : parseInt(String(b.year || 0), 10);
  const yearB = Number.isFinite(parsedYearB) ? parsedYearB : 0;
  if (yearB !== yearA) return yearB - yearA;

  // 2. Date added descending; if no date added, fallback to original photo date descending
  const addedA = parseDateValue(a.added ?? a.addedAt);
  const photoDateA = parseDateValue(a.photoDate ?? a.photo_date ?? a.photoTimestamp);
  const dateA = addedA || photoDateA;

  const addedB = parseDateValue(b.added ?? b.addedAt);
  const photoDateB = parseDateValue(b.photoDate ?? b.photo_date ?? b.photoTimestamp);
  const dateB = addedB || photoDateB;

  if (dateB !== dateA) return dateB - dateA;

  // 3. Tie-breakers: title ascending, id ascending
  const titleDiff = titleA.localeCompare(titleB, 'ru', { sensitivity: 'accent' });
  if (titleDiff !== 0) return titleDiff;
  return idA.localeCompare(idB);
}
