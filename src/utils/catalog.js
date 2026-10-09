/**
 * Normalizes text for case-insensitive and character-agnostic comparison:
 * lowercase, 'ё' -> 'е', and trimmed.
 *
 * @param {string} text
 * @returns {string}
 */
export function normalize(text) {
  return (text || '').toLowerCase().replace(/ё/g, 'е').trim();
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
  if (!searchQuery) return true;
  const normalizedQuery = normalize(searchQuery);
  if (!normalizedQuery) return true;

  const title = normalize(book.title || '');
  const author = normalize(book.author || '');
  const isbn = normalize(book.isbn || '');

  const cleanIsbn = isbn.replace(/^isbn[:\s]*/i, '').replace(/[-\s\u2010-\u2015]/g, '');
  const cleanQuery = normalizedQuery.replace(/^isbn[:\s]*/i, '').replace(/[-\s\u2010-\u2015]/g, '');
  const queryWords = normalizedQuery.split(/\s+/).filter(Boolean);

  const matchesAllWords = queryWords.length > 0 && queryWords.every(
    (word) => title.includes(word) || author.includes(word)
  );

  return matchesAllWords || (cleanQuery.length > 0 && cleanIsbn.includes(cleanQuery));
}

/**
 * Checks if a book matches a selected genre.
 *
 * @param {{ genres?: string | string[] }} book
 * @param {string} selectedGenre
 * @returns {boolean}
 */
export function matchesGenre(book, selectedGenre) {
  if (!selectedGenre) return true;
  const normalizedGenre = normalize(selectedGenre);
  if (!normalizedGenre) return true;

  const genresRaw = Array.isArray(book.genres)
    ? book.genres.join(',')
    : (book.genres || '');
  const normalizedGenres = normalize(genresRaw);
  const itemGenres = normalizedGenres.split(',').map((g) => g.trim());

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
  return matchesSearch(book, searchQuery) && matchesGenre(book, selectedGenre);
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
  if (sortMode === 'title') {
    const titleDiff = (a.title || '').localeCompare(b.title || '', 'ru');
    if (titleDiff !== 0) return titleDiff;
    const authorDiff = (a.author || '').localeCompare(b.author || '', 'ru');
    if (authorDiff !== 0) return authorDiff;
    return (a.id || '').localeCompare(b.id || '');
  }

  if (sortMode === 'author') {
    const authorA = (a.author || '').trim();
    const authorB = (b.author || '').trim();
    if (!authorA && authorB) return 1;
    if (authorA && !authorB) return -1;
    const authorDiff = authorA.localeCompare(authorB, 'ru');
    if (authorDiff !== 0) return authorDiff;
    const titleDiff = (a.title || '').localeCompare(b.title || '', 'ru');
    if (titleDiff !== 0) return titleDiff;
    return (a.id || '').localeCompare(b.id || '');
  }

  // "recent" mode: sort by date added descending (DESIGN.md 8.2), tie-breakers: year desc, title asc
  const addedA = typeof a.added === 'number' ? a.added : parseInt(String(a.added || 0), 10);
  const addedB = typeof b.added === 'number' ? b.added : parseInt(String(b.added || 0), 10);
  if (addedB !== addedA) {
    return addedB - addedA;
  }

  const yearA = typeof a.year === 'number' ? a.year : parseInt(String(a.year || 0), 10);
  const yearB = typeof b.year === 'number' ? b.year : parseInt(String(b.year || 0), 10);
  if (yearB !== yearA) {
    return yearB - yearA;
  }

  return (a.title || '').localeCompare(b.title || '', 'ru');
}
