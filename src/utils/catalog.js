/**
 * Normalizes text for case-insensitive and character-agnostic comparison:
 * lowercase, 'ё' -> 'е', and trimmed.
 *
 * @param {string} text
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
    .replace(/^isbn(?:-?1[03])?[:\s]*/i, '')
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

  const title = normalize(book.title || '');
  const author = normalize(book.author || '');
  const cleanIsbnValue = cleanIsbn(book.isbn);
  const cleanQuery = cleanIsbn(normalizedQuery);
  const queryWords = normalizedQuery.split(/\s+/).filter(Boolean);

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

function parseDateValue(val) {
  if (typeof val === 'number') return Number.isFinite(val) ? val : 0;
  const num = Number(val);
  if (Number.isFinite(num)) return num;
  const parsed = Date.parse(String(val || ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Sort comparator for catalog books.
 * Supported modes: 'recent', 'title', 'author'.
 *
 * @param {{ id?: string; title?: string; author?: string; added?: number | string; year?: number | string }} a
 * @param {{ id?: string; title?: string; author?: string; added?: number | string; year?: number | string }} b
 * @param {string} [sortMode='recent']
 * @returns {number}
 */
export function compareBooks(a, b, sortMode = 'recent') {
  a = a || {};
  b = b || {};

  const titleA = String(a.title ?? '');
  const titleB = String(b.title ?? '');
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

  // "recent" mode: sort by date added descending (DESIGN.md 8.2), tie-breakers: year desc, title asc, id asc
  const addedA = parseDateValue(a.added);
  const addedB = parseDateValue(b.added);
  if (addedB !== addedA) return addedB - addedA;

  const parsedYearA = typeof a.year === 'number' ? a.year : parseInt(String(a.year || 0), 10);
  const yearA = Number.isFinite(parsedYearA) ? parsedYearA : 0;
  const parsedYearB = typeof b.year === 'number' ? b.year : parseInt(String(b.year || 0), 10);
  const yearB = Number.isFinite(parsedYearB) ? parsedYearB : 0;
  if (yearB !== yearA) return yearB - yearA;

  const titleDiff = titleA.localeCompare(titleB, 'ru', { sensitivity: 'accent' });
  if (titleDiff !== 0) return titleDiff;
  return idA.localeCompare(idB);
}
