import test from 'node:test';
import assert from 'node:assert/strict';
import {
  normalize,
  matchesSearch,
  matchesGenre,
  matchesFilter,
  compareBooks,
} from '../src/utils/catalog.js';

test('1. Строковая нормализация (normalize)', async (t) => {
  await t.test('переводит строку в нижний регистр', () => {
    assert.equal(normalize('КОМПЬЮТЕР С science'), 'компьютер с science');
  });

  await t.test('заменяет букву «ё» на «е»', () => {
    assert.equal(normalize('Пётр и смышлёный ёж'), 'петр и смышленый еж');
    assert.equal(normalize('Ёлка Зелёная'), 'елка зеленая');
  });

  await t.test('удаляет пробелы по краям (trim)', () => {
    assert.equal(normalize('   Гарри Поттер   '), 'гарри поттер');
  });

  await t.test('обрабатывает пустые строки и null/undefined', () => {
    assert.equal(normalize(''), '');
    assert.equal(normalize(null), '');
    assert.equal(normalize(undefined), '');
  });

  await t.test('корректно приводит числа и другие нестроковые типы (включая 0 и 12345)', () => {
    assert.equal(normalize(12345), '12345');
    assert.equal(normalize(0), '0');
    assert.equal(normalize(false), 'false');
  });
});

test('2. Мультисловный поиск по названию и автору (matchesSearch)', async (t) => {
  const sampleBook = {
    title: 'Теоретический минимум по Computer Science',
    author: 'Владстон Феррейра Фило',
    isbn: '978-5-4461-0923-4',
  };

  await t.test('находит книгу по одному слову из названия', () => {
    assert.equal(matchesSearch(sampleBook, 'теоретический'), true);
    assert.equal(matchesSearch(sampleBook, 'computer'), true);
  });

  await t.test('находит книгу по автору', () => {
    assert.equal(matchesSearch(sampleBook, 'Феррейра'), true);
  });

  await t.test('находит книгу при распределении слов запроса между названием и автором', () => {
    // «минимум» в названии, «фило» в авторе
    assert.equal(matchesSearch(sampleBook, 'минимум фило'), true);
    // «владстон» в авторе, «science» в названии
    assert.equal(matchesSearch(sampleBook, 'science владстон'), true);
  });

  await t.test('возвращает false, если хотя бы одно слово запроса не найдено', () => {
    assert.equal(matchesSearch(sampleBook, 'минимум толстой'), false);
    assert.equal(matchesSearch(sampleBook, 'python rust'), false);
  });

  await t.test('учитывает нормализацию «ё» / «е» при поиске', () => {
    const bookWithYo = {
      title: 'Пётр Первый',
      author: 'Алексей Толстой',
      isbn: '978-5-17-000000-0',
    };
    assert.equal(matchesSearch(bookWithYo, 'петр первый'), true);
    assert.equal(matchesSearch(bookWithYo, 'пётр первый'), true);
  });

  await t.test('пустой запрос возвращает true', () => {
    assert.equal(matchesSearch(sampleBook, ''), true);
    assert.equal(matchesSearch(sampleBook, '   '), true);
  });
});

test('3. Поиск по ISBN (очистка дефисов и пробелов)', async (t) => {
  const book = {
    title: 'Computer Science для программиста-самоучки',
    author: 'Кори Альтхофф',
    isbn: '978-5-04-110057-5',
  };

  await t.test('находит книгу по чистому ISBN без дефисов', () => {
    assert.equal(matchesSearch(book, '9785041100575'), true);
  });

  await t.test('находит книгу по ISBN с дефисами', () => {
    assert.equal(matchesSearch(book, '978-5-04-110057-5'), true);
  });

  await t.test('находит книгу по частичному или разбитому пробелами ISBN', () => {
    assert.equal(matchesSearch(book, '978 5 04 110057 5'), true);
    assert.equal(matchesSearch(book, '5041100575'), true);
  });

  await t.test('находит книгу по запросу с типографскими тире (en-dash, em-dash)', () => {
    assert.equal(matchesSearch(book, '978–5–04–110057–5'), true);
    assert.equal(matchesSearch(book, '978—5—04—110057—5'), true);
  });

  await t.test('находит книгу по запросу с математическим минусом (U+2212)', () => {
    assert.equal(matchesSearch(book, '978−5−04−110057−5'), true);
  });

  await t.test('находит книгу, если ISBN в объекте книги содержит математический минус (U+2212)', () => {
    const bookWithMinus = { ...book, isbn: '978−5−04−110057−5' };
    assert.equal(matchesSearch(bookWithMinus, '978-5-04-110057-5'), true);
    assert.equal(matchesSearch(bookWithMinus, '9785041100575'), true);
  });

  await t.test('находит книгу по запросу с префиксом ISBN', () => {
    assert.equal(matchesSearch(book, 'ISBN 978-5-04-110057-5'), true);
    assert.equal(matchesSearch(book, 'isbn: 978-5-04-110057-5'), true);
    assert.equal(matchesSearch(book, 'ISBN: 978–5–04–110057–5'), true);
  });

  await t.test('находит книгу по запросу с префиксами ISBN-13 и ISBN-10', () => {
    assert.equal(matchesSearch(book, 'ISBN-13: 978-5-04-110057-5'), true);
    assert.equal(matchesSearch(book, 'isbn-13: 978-5-04-110057-5'), true);
    assert.equal(matchesSearch(book, 'ISBN13: 978-5-04-110057-5'), true);
    assert.equal(matchesSearch(book, 'isbn13 9785041100575'), true);

    const book10 = {
      title: 'Computer Science для программиста-самоучки',
      author: 'Кори Альтхофф',
      isbn: '5-04-110057-5',
    };
    assert.equal(matchesSearch(book10, 'ISBN-10: 5-04-110057-5'), true);
    assert.equal(matchesSearch(book10, 'isbn-10: 5-04-110057-5'), true);
    assert.equal(matchesSearch(book10, 'ISBN10: 5-04-110057-5'), true);
    assert.equal(matchesSearch(book10, 'isbn10 5041100575'), true);
  });

  await t.test('возвращает false при несовпадающем ISBN', () => {
    assert.equal(matchesSearch(book, '9781234567890'), false);
  });
});

test('4. Фильтрация по ярлыкам (matchesGenre)', async (t) => {
  const book = {
    title: 'Дизайн для недизайнеров',
    genres: ['дизайн', 'типографика'],
  };

  await t.test('находит книгу по точному совпадению ярлыка', () => {
    assert.equal(matchesGenre(book, 'дизайн'), true);
    assert.equal(matchesGenre(book, 'типографика'), true);
  });

  await t.test('учитывает регистр и букву «ё»', () => {
    const bookYo = { title: 'Книга', genres: ['верстка и типографика'] };
    assert.equal(matchesGenre(bookYo, 'ВЕРСТКА И ТИПОГРАФИКА'), true);
  });

  await t.test('возвращает false при отсутствии ярлыка', () => {
    assert.equal(matchesGenre(book, 'программирование'), false);
  });

  await t.test('пустой ярлык возвращает true', () => {
    assert.equal(matchesGenre(book, ''), true);
  });

  await t.test('проверяет комбинированную фильтрацию по поиску и ярлыку (matchesFilter)', () => {
    assert.equal(matchesFilter(book, 'дизайн', 'дизайн'), true);
    assert.equal(matchesFilter(book, 'дизайн', 'программирование'), false);
    assert.equal(matchesFilter(book, 'математика', 'дизайн'), false);
  });

  await t.test('поддерживает строковое представление жанров через запятую из dataset', () => {
    const datasetBook = {
      title: 'Дизайн для недизайнеров',
      author: 'Робин Уильямс',
      isbn: '978-5-00000-000-0',
      genres: 'дизайн,типографика,компьютерные науки',
    };
    assert.equal(matchesGenre(datasetBook, 'типографика'), true);
    assert.equal(matchesGenre(datasetBook, 'компьютерные науки'), true);
    assert.equal(matchesGenre(datasetBook, 'программирование'), false);
    assert.equal(matchesFilter(datasetBook, 'робин', 'типографика'), true);
    assert.equal(matchesFilter(datasetBook, 'толстой', 'типографика'), false);
  });

  await t.test('корректно фильтрует жанры, содержащие запятые в названии', () => {
    const bookWithCommaGenre = {
      title: 'Энциклопедия',
      genres: ['Наука, образование', 'Справочники'],
    };
    assert.equal(matchesGenre(bookWithCommaGenre, 'Наука, образование'), true);
    assert.equal(matchesGenre(bookWithCommaGenre, 'наука, образование'), true);
    assert.equal(matchesGenre(bookWithCommaGenre, 'Наука'), false);
    assert.equal(matchesGenre(bookWithCommaGenre, 'образование'), false);
  });

  await t.test('поддерживает сериализованный JSON-массив жанров из data-genres', () => {
    const bookJsonGenres = {
      title: 'Научная книга',
      genres: JSON.stringify(['Наука, образование', 'ИТ']),
    };
    assert.equal(matchesGenre(bookJsonGenres, 'Наука, образование'), true);
    assert.equal(matchesGenre(bookJsonGenres, 'ИТ'), true);
    assert.equal(matchesGenre(bookJsonGenres, 'Наука'), false);
  });
});

test('5. Компараторы сортировки (compareBooks)', async (t) => {
  const books = [
    {
      id: 'book-1',
      title: 'Дизайн для недизайнеров',
      author: 'Робин Уильямс',
      added: 1710000000,
      year: 2018,
    },
    {
      id: 'book-2',
      title: 'Теоретический минимум по Computer Science',
      author: 'Владстон Феррейра Фило',
      added: 1720000000,
      year: 2019,
    },
    {
      id: 'book-3',
      title: 'Computer Science для программиста-самоучки',
      author: 'Кори Альтхофф',
      added: 1700000000,
      year: 2021,
    },
    {
      id: 'book-4',
      title: 'Сам себе программист',
      author: 'Кори Альтхофф',
      added: 1700000000,
      year: 2022,
    },
  ];

  await t.test('сортировка «recent» (по дате добавления desc, tie-break по году desc, затем по названию)', () => {
    const fixtureBooks = [
      ...books,
      {
        id: 'book-5',
        title: 'Абстракция данных',
        author: 'Кори Альтхофф',
        added: 1700000000,
        year: 2021,
      },
    ];
    const sorted = [...fixtureBooks].sort((a, b) => compareBooks(a, b, 'recent'));
    // book-2 (added: 1720000000) -> book-1 (added: 1710000000) ->
    // book-4 (added: 1700000000, year 2022) ->
    // book-5 (added: 1700000000, year 2021, 'Абстракция...') ->
    // book-3 (added: 1700000000, year 2021, 'Computer Science...')
    assert.deepEqual(sorted.map((b) => b.id), ['book-2', 'book-1', 'book-4', 'book-5', 'book-3']);
  });

  await t.test('сортировка «title» (по названию А-Я)', () => {
    const sorted = [...books].sort((a, b) => compareBooks(a, b, 'title'));
    // В русской локали кириллица предшествует латинице:
    // 'Дизайн для недизайнеров' -> 'Сам себе программист' -> 'Теоретический минимум...' -> 'Computer Science...'
    assert.deepEqual(sorted.map((b) => b.id), ['book-1', 'book-4', 'book-2', 'book-3']);
  });

  await t.test('сортировка «author» (по автору А-Я)', () => {
    const sorted = [...books].sort((a, b) => compareBooks(a, b, 'author'));
    // Владстон Феррейра Фило -> Кори Альтхофф (x2) -> Робин Уильямс
    assert.equal(sorted[0].id, 'book-2'); // Владстон
    assert.equal(sorted[3].id, 'book-1'); // Робин
    // Для двух книг Кори Альтхоффа tie-break идет по названию:
    // 'Сам себе программист' (кириллица С) идет перед 'Computer Science...' (латиница C)
    assert.equal(sorted[1].id, 'book-4');
    assert.equal(sorted[2].id, 'book-3');
  });

  await t.test('сортировка «author» размещает книги без автора в конце', () => {
    const booksWithAuthorless = [
      { id: 'no-author-1', title: 'Языки программирования', author: '' },
      { id: 'with-author-1', title: 'Алиса в Стране чудес', author: 'Льюис Кэрролл' },
      { id: 'no-author-2', title: 'Алгоритмы', author: '   ' },
      { id: 'with-author-2', title: 'Война и мир', author: 'Лев Толстой' },
      { id: 'no-author-3', title: 'Библия', author: undefined },
    ];
    const sorted = [...booksWithAuthorless].sort((a, b) => compareBooks(a, b, 'author'));
    // Книги с автором:
    // 'Лев Толстой' ('with-author-2') -> 'Льюис Кэрролл' ('with-author-1')
    // Книги без автора (отсортированы по названию А-Я):
    // 'Алгоритмы' ('no-author-2') -> 'Библия' ('no-author-3') -> 'Языки программирования' ('no-author-1')
    assert.deepEqual(sorted.map((b) => b.id), [
      'with-author-2',
      'with-author-1',
      'no-author-2',
      'no-author-3',
      'no-author-1',
    ]);
  });

  await t.test('сортировка работает корректно со строковыми dataset-атрибутами', () => {
    const datasetBooks = [
      { id: 'b-1', title: 'Язык C', author: 'Керниган', added: '1700000000', year: '1988' },
      { id: 'b-2', title: 'Алгоритмы', author: 'Кормен', added: '1720000000', year: '2020' },
      { id: 'b-3', title: 'Чистый код', author: 'Мартин', added: '1710000000', year: '2019' },
    ];
    const sortedRecent = [...datasetBooks].sort((a, b) => compareBooks(a, b, 'recent'));
    assert.deepEqual(sortedRecent.map((b) => b.id), ['b-2', 'b-3', 'b-1']);

    const sortedTitle = [...datasetBooks].sort((a, b) => compareBooks(a, b, 'title'));
    assert.deepEqual(sortedTitle.map((b) => b.id), ['b-2', 'b-3', 'b-1']); // Алгоритмы -> Чистый код -> Язык C

    const sortedAuthor = [...datasetBooks].sort((a, b) => compareBooks(a, b, 'author'));
    assert.deepEqual(sortedAuthor.map((b) => b.id), ['b-1', 'b-2', 'b-3']); // Керниган -> Кормен -> Мартин
  });

  await t.test('сортировка «recent» корректно сравнивает ISO-строки дат (2026-01-15 vs 2026-11-20)', () => {
    const isoBooks = [
      { id: 'b-jan', title: 'Январская книга', added: '2026-01-15', year: 2026 },
      { id: 'b-nov', title: 'Ноябрьская книга', added: '2026-11-20', year: 2026 },
      { id: 'b-mar', title: 'Мартовская книга', added: '2026-03-10', year: 2026 },
    ];
    const sorted = [...isoBooks].sort((a, b) => compareBooks(a, b, 'recent'));
    // Убывающий порядок: 2026-11-20 -> 2026-03-10 -> 2026-01-15
    assert.deepEqual(sorted.map((b) => b.id), ['b-nov', 'b-mar', 'b-jan']);
  });

  await t.test('тай-брейк по id при совпадающих названии и авторе', () => {
    const identicalBooks = [
      { id: 'b-z', title: 'Дубликат', author: 'Автор', added: 100, year: 2020 },
      { id: 'b-a', title: 'Дубликат', author: 'Автор', added: 100, year: 2020 },
    ];
    const sortedTitle = [...identicalBooks].sort((a, b) => compareBooks(a, b, 'title'));
    assert.deepEqual(sortedTitle.map((b) => b.id), ['b-a', 'b-z']);

    const sortedAuthor = [...identicalBooks].sort((a, b) => compareBooks(a, b, 'author'));
    assert.deepEqual(sortedAuthor.map((b) => b.id), ['b-a', 'b-z']);
  });

  await t.test('тай-брейк по id в «recent» при одинаковых added, year и title', () => {
    const identicalRecent = [
      { id: 'book-z', title: 'Одинаковая книга', author: 'Автор', added: 1500, year: 2021 },
      { id: 'book-a', title: 'Одинаковая книга', author: 'Автор', added: 1500, year: 2021 },
    ];
    const sortedRecent = [...identicalRecent].sort((a, b) => compareBooks(a, b, 'recent'));
    assert.deepEqual(sortedRecent.map((b) => b.id), ['book-a', 'book-z']);
  });

  await t.test('тай-брейк по автору в «title» при одинаковых названиях', () => {
    const sameTitleBooks = [
      { id: 'b-chekhov', title: 'Избранное', author: 'Чехов Антон' },
      { id: 'b-bunin', title: 'Избранное', author: 'Бунин Иван' },
      { id: 'b-dostoevsky', title: 'Избранное', author: 'Достоевский Федор' },
    ];
    const sorted = [...sameTitleBooks].sort((a, b) => compareBooks(a, b, 'title'));
    assert.deepEqual(sorted.map((b) => b.id), ['b-bunin', 'b-dostoevsky', 'b-chekhov']);
  });

  await t.test('детерминированная сортировка при нечисловых / NaN значениях added и year', () => {
    const dirtyBooks = [
      { id: 'b-valid', title: 'Азбука', added: 500, year: 2020 },
      { id: 'b-nan-added-2', title: 'Ярмарка', added: 'not-a-number', year: 2020 },
      { id: 'b-nan-added-1', title: 'Басни', added: NaN, year: 2020 },
      { id: 'b-nan-year', title: 'Гармония', added: 0, year: 'invalid-year' },
    ];
    const sortedRecent = [...dirtyBooks].sort((a, b) => compareBooks(a, b, 'recent'));
    assert.deepEqual(sortedRecent.map((b) => b.id), [
      'b-valid',
      'b-nan-added-1',
      'b-nan-added-2',
      'b-nan-year',
    ]);
  });
});

test('6. Защитная обработка null / undefined объектов книг', async (t) => {
  await t.test('matchesSearch возвращает false для null и undefined', () => {
    assert.equal(matchesSearch(null, 'поиск'), false);
    assert.equal(matchesSearch(undefined, 'поиск'), false);
    assert.equal(matchesSearch(null, ''), false);
    assert.equal(matchesSearch(undefined, ''), false);
  });

  await t.test('matchesGenre корректно обрабатывает null и undefined', () => {
    assert.equal(matchesGenre(null, 'дизайн'), false);
    assert.equal(matchesGenre(undefined, 'дизайн'), false);
    assert.equal(matchesGenre(null, ''), true);
    assert.equal(matchesGenre(undefined, ''), true);
  });

  await t.test('matchesFilter возвращает false для null и undefined', () => {
    assert.equal(matchesFilter(null, 'поиск', 'дизайн'), false);
    assert.equal(matchesFilter(undefined, 'поиск', 'дизайн'), false);
    assert.equal(matchesFilter(null, '', ''), false);
    assert.equal(matchesFilter(undefined, '', ''), false);
  });

  await t.test('compareBooks устойчив к null и undefined аргументам', () => {
    const sample = { id: 'sample', title: 'Книга', author: 'Автор', added: 100, year: 2020 };
    assert.doesNotThrow(() => compareBooks(null, null, 'recent'));
    assert.doesNotThrow(() => compareBooks(null, sample, 'recent'));
    assert.doesNotThrow(() => compareBooks(sample, null, 'recent'));
    assert.doesNotThrow(() => compareBooks(undefined, sample, 'title'));
    assert.doesNotThrow(() => compareBooks(sample, undefined, 'author'));

    assert.equal(compareBooks(null, null, 'recent'), 0);
    assert.equal(compareBooks(null, null, 'title'), 0);
    assert.equal(compareBooks(null, null, 'author'), 0);
  });
});
