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

  await t.test('находит книгу по запросу с префиксом ISBN', () => {
    assert.equal(matchesSearch(book, 'ISBN 978-5-04-110057-5'), true);
    assert.equal(matchesSearch(book, 'isbn: 978-5-04-110057-5'), true);
    assert.equal(matchesSearch(book, 'ISBN: 978–5–04–110057–5'), true);
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
});
