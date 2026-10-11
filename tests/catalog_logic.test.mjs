import test from 'node:test';
import assert from 'node:assert/strict';
import {
  normalize,
  cleanIsbn,
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

  await t.test('находит книгу, когда title равен 0 при поиске "0"', () => {
    const bookWithZeroTitle = { title: 0, author: 'Автор' };
    assert.equal(matchesSearch(bookWithZeroTitle, '0'), true);
    assert.equal(matchesSearch(bookWithZeroTitle, 'автор'), true);
  });

  await t.test('работает корректно, когда book.isbn undefined, null или опущен (поиск по названию/автору и числовым запросам)', () => {
    const bookNoIsbn = { title: '1984', author: 'Джордж Оруэлл' };
    const bookNullIsbn = { title: '1984', author: 'Джордж Оруэлл', isbn: null };
    const bookUndefIsbn = { title: '1984', author: 'Джордж Оруэлл', isbn: undefined };

    assert.equal(matchesSearch(bookNoIsbn, 'оруэлл'), true);
    assert.equal(matchesSearch(bookNoIsbn, '1984'), true);
    assert.equal(matchesSearch(bookNoIsbn, 'оруэлл 1984'), true);
    assert.equal(matchesSearch(bookNoIsbn, 'толстой'), false);

    assert.equal(matchesSearch(bookNullIsbn, 'оруэлл'), true);
    assert.equal(matchesSearch(bookNullIsbn, '1984'), true);
    assert.equal(matchesSearch(bookNullIsbn, 'несуществующее'), false);

    assert.equal(matchesSearch(bookUndefIsbn, 'оруэлл'), true);
    assert.equal(matchesSearch(bookUndefIsbn, '1984'), true);
    assert.equal(matchesSearch(bookUndefIsbn, 'несуществующее'), false);
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
    assert.equal(matchesSearch(book, 'ISBN 13: 978-5-04-110057-5'), true);
    assert.equal(matchesSearch(book, 'isbn 13: 978-5-04-110057-5'), true);

    const book10 = {
      title: 'Computer Science для программиста-самоучки',
      author: 'Кори Альтхофф',
      isbn: '5-04-110057-5',
    };
    assert.equal(matchesSearch(book10, 'ISBN-10: 5-04-110057-5'), true);
    assert.equal(matchesSearch(book10, 'isbn-10: 5-04-110057-5'), true);
    assert.equal(matchesSearch(book10, 'ISBN10: 5-04-110057-5'), true);
    assert.equal(matchesSearch(book10, 'isbn10 5041100575'), true);
    assert.equal(matchesSearch(book10, 'ISBN 10: 5-04-110057-5'), true);
    assert.equal(matchesSearch(book10, 'isbn 10: 5-04-110057-5'), true);
  });

  await t.test('находит книгу, если ISBN в объекте книги содержит префиксы (ISBN, ISBN-13, ISBN-10)', () => {
    const bookWithPrefix13 = {
      title: 'Computer Science для программиста-самоучки',
      author: 'Кори Альтхофф',
      isbn: 'ISBN-13: 978-5-04-110057-5',
    };
    const bookWithSpacePrefix13 = {
      ...bookWithPrefix13,
      isbn: 'ISBN 13: 978-5-04-110057-5',
    };
    const bookWithPrefixPlain = {
      ...bookWithPrefix13,
      isbn: 'ISBN: 978-5-04-110057-5',
    };
    const bookWithPrefix10 = {
      ...bookWithPrefix13,
      isbn: 'ISBN-10: 5-04-110057-5',
    };
    const bookWithSpacePrefix10 = {
      ...bookWithPrefix13,
      isbn: 'ISBN 10: 5-04-110057-5',
    };

    assert.equal(matchesSearch(bookWithPrefix13, '9785041100575'), true);
    assert.equal(matchesSearch(bookWithPrefix13, '978-5-04-110057-5'), true);

    assert.equal(matchesSearch(bookWithSpacePrefix13, '9785041100575'), true);
    assert.equal(matchesSearch(bookWithSpacePrefix13, '978-5-04-110057-5'), true);

    assert.equal(matchesSearch(bookWithPrefixPlain, '9785041100575'), true);
    assert.equal(matchesSearch(bookWithPrefixPlain, '978-5-04-110057-5'), true);

    assert.equal(matchesSearch(bookWithPrefix10, '5041100575'), true);
    assert.equal(matchesSearch(bookWithPrefix10, '5-04-110057-5'), true);

    assert.equal(matchesSearch(bookWithSpacePrefix10, '5041100575'), true);
    assert.equal(matchesSearch(bookWithSpacePrefix10, '5-04-110057-5'), true);
  });

  await t.test('корректно обрабатывает контрольную цифру "X" / "x" в ISBN-10', () => {
    const bookWithX = {
      title: 'Design Patterns',
      author: 'Erich Gamma',
      isbn: '0-201-63361-X',
    };
    assert.equal(matchesSearch(bookWithX, '0-201-63361-X'), true);
    assert.equal(matchesSearch(bookWithX, '020163361x'), true);
    assert.equal(matchesSearch(bookWithX, '020163361X'), true);
    assert.equal(matchesSearch(bookWithX, '0-201-63361-x'), true);
    assert.equal(matchesSearch(bookWithX, 'ISBN-10: 0-201-63361-X'), true);
    assert.equal(matchesSearch(bookWithX, 'ISBN 10: 0-201-63361-x'), true);
    assert.equal(matchesSearch(bookWithX, '63361x'), true);
    assert.equal(matchesSearch(bookWithX, '63361X'), true);

    const bookWithLowerX = {
      ...bookWithX,
      isbn: '020163361x',
    };
    assert.equal(matchesSearch(bookWithLowerX, '0-201-63361-X'), true);
    assert.equal(matchesSearch(bookWithLowerX, '020163361x'), true);
  });

  await t.test('обрабатывает книги без ISBN (undefined, null или опущен) при числовых запросах и поиске по ISBN', () => {
    const bookNoIsbn = { title: 'О дивный новый мир', author: 'Олдос Хаксли' };
    const bookNullIsbn = { title: 'О дивный новый мир', author: 'Олдос Хаксли', isbn: null };
    const bookUndefIsbn = { title: 'О дивный новый мир', author: 'Олдос Хаксли', isbn: undefined };

    // Числовой запрос из 4+ цифр не должен ошибочно матчить книгу без ISBN, если его нет в названии/авторе
    assert.equal(matchesSearch(bookNoIsbn, '1984'), false);
    assert.equal(matchesSearch(bookNullIsbn, '1984'), false);
    assert.equal(matchesSearch(bookUndefIsbn, '1984'), false);

    // Запрос с префиксом ISBN не должен матчить книгу без ISBN
    assert.equal(matchesSearch(bookNoIsbn, 'ISBN 978-5-04-110057-5'), false);
    assert.equal(matchesSearch(bookNullIsbn, 'ISBN 978-5-04-110057-5'), false);
    assert.equal(matchesSearch(bookUndefIsbn, 'ISBN 978-5-04-110057-5'), false);

    // Если числовой запрос '1984' содержится в названии книги без ISBN — успешно находит по названию
    const book1984NoIsbn = { title: '1984', author: 'Джордж Оруэлл' };
    assert.equal(matchesSearch(book1984NoIsbn, '1984'), true);
    assert.equal(matchesSearch({ title: '1984', author: 'Джордж Оруэлл', isbn: null }, '1984'), true);
    assert.equal(matchesSearch({ title: '1984', author: 'Джордж Оруэлл', isbn: undefined }, '1984'), true);
  });

  await t.test('возвращает false при несовпадающем ISBN', () => {
    assert.equal(matchesSearch(book, '9781234567890'), false);
  });

  await t.test('поиск по одиночной цифре (1-3 цифры) не матчит ISBN без префикса isbn', () => {
    // В названии и авторе нет '9', но есть в ISBN '978-5-04-110057-5'
    assert.equal(matchesSearch(book, '9'), false);
    assert.equal(matchesSearch(book, '97'), false);
    assert.equal(matchesSearch(book, '978'), false);
  });

  await t.test('поиск по 4+ цифрам из ISBN или с префиксом isbn успешно находит книгу по ISBN', () => {
    assert.equal(matchesSearch(book, '9785'), true);
    assert.equal(matchesSearch(book, '5041100575'), true);
    assert.equal(matchesSearch(book, 'isbn: 9'), true);
  });

  await t.test('cleanIsbn очищает префиксы ISBN, ISBN-10, ISBN-13, пробелы и все виды дефисов', () => {
    assert.equal(cleanIsbn('978-5-04-110057-5'), '9785041100575');
    assert.equal(cleanIsbn('ISBN-13: 978-5-04-110057-5'), '9785041100575');
    assert.equal(cleanIsbn('ISBN 13: 978-5-04-110057-5'), '9785041100575');
    assert.equal(cleanIsbn('isbn 13: 978-5-04-110057-5'), '9785041100575');
    assert.equal(cleanIsbn('isbn13: 978 5 04 110057 5'), '9785041100575');
    assert.equal(cleanIsbn('ISBN-10: 5-04-110057-5'), '5041100575');
    assert.equal(cleanIsbn('ISBN 10: 5-04-110057-5'), '5041100575');
    assert.equal(cleanIsbn('isbn 10: 5-04-110057-5'), '5041100575');
    assert.equal(cleanIsbn('0-201-63361-X'), '020163361x');
    assert.equal(cleanIsbn('020163361x'), '020163361x');
    assert.equal(cleanIsbn('ISBN-10: 0-201-63361-X'), '020163361x');
    assert.equal(cleanIsbn('ISBN 10: 0-201-63361-x'), '020163361x');
    assert.equal(cleanIsbn('ISBN 978–5–04–110057–5'), '9785041100575');
    assert.equal(cleanIsbn('978−5−04−110057−5'), '9785041100575');
    assert.equal(cleanIsbn(''), '');
    assert.equal(cleanIsbn(null), '');
    assert.equal(cleanIsbn(undefined), '');
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

  await t.test('поддерживает bracketed строки без валидного JSON', () => {
    const bookBracketPlain = {
      title: 'Книга 1',
      genres: '[дизайн, типографика]',
    };
    assert.equal(matchesGenre(bookBracketPlain, 'дизайн'), true);
    assert.equal(matchesGenre(bookBracketPlain, 'типографика'), true);
    assert.equal(matchesGenre(bookBracketPlain, 'программирование'), false);

    const bookBracketSingleQuotes = {
      title: 'Книга 2',
      genres: "['дизайн', 'типографика']",
    };
    assert.equal(matchesGenre(bookBracketSingleQuotes, 'дизайн'), true);
    assert.equal(matchesGenre(bookBracketSingleQuotes, 'типографика'), true);
    assert.equal(matchesGenre(bookBracketSingleQuotes, 'программирование'), false);
  });

  await t.test('обрабатывает книги с отсутствующим или пустым полем genres (undefined, null или опущено)', () => {
    const bookNoGenres = { title: 'Книга без поля genres' };
    const bookNullGenres = { title: 'Книга с null genres', genres: null };
    const bookUndefGenres = { title: 'Книга с undefined genres', genres: undefined };

    assert.equal(matchesGenre(bookNoGenres, 'дизайн'), false);
    assert.equal(matchesGenre(bookNoGenres, ''), true);

    assert.equal(matchesGenre(bookNullGenres, 'дизайн'), false);
    assert.equal(matchesGenre(bookNullGenres, ''), true);

    assert.equal(matchesGenre(bookUndefGenres, 'дизайн'), false);
    assert.equal(matchesGenre(bookUndefGenres, ''), true);
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

  await t.test('сортировка «recent» корректно сравнивает Date объекты в поле added', () => {
    const dateBooks = [
      { id: 'b-may', title: 'Майская книга', added: new Date('2026-05-01T00:00:00Z'), year: 2026 },
      { id: 'b-dec', title: 'Декабрьская книга', added: new Date('2026-12-01T00:00:00Z'), year: 2026 },
      { id: 'b-jan', title: 'Январская книга', added: new Date('2026-01-01T00:00:00Z'), year: 2026 },
    ];
    const sorted = [...dateBooks].sort((a, b) => compareBooks(a, b, 'recent'));
    // Убывающий порядок: 2026-12-01 -> 2026-05-01 -> 2026-01-01
    assert.deepEqual(sorted.map((b) => b.id), ['b-dec', 'b-may', 'b-jan']);

    const mixedBooks = [
      { id: 'b-date', title: 'Книга Date', added: new Date('2026-06-01T00:00:00Z') },
      { id: 'b-timestamp', title: 'Книга Timestamp', added: new Date('2026-07-01T00:00:00Z').getTime() },
      { id: 'b-iso', title: 'Книга ISO', added: '2026-05-01T00:00:00Z' },
    ];
    const sortedMixed = [...mixedBooks].sort((a, b) => compareBooks(a, b, 'recent'));
    assert.deepEqual(sortedMixed.map((b) => b.id), ['b-timestamp', 'b-date', 'b-iso']);
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

  await t.test('compareBooks корректно работает и не падает с TypeError с числовыми id ({ id: 101 }), title ({ title: 1984 }) и author', () => {
    const numBooks = [
      { id: 102, title: 1984, author: 'Джордж Оруэлл' },
      { id: 101, title: 'Аэлита', author: 0 },
    ];
    assert.doesNotThrow(() => [...numBooks].sort((a, b) => compareBooks(a, b, 'title')));
    assert.doesNotThrow(() => [...numBooks].sort((a, b) => compareBooks(a, b, 'author')));
    assert.doesNotThrow(() => [...numBooks].sort((a, b) => compareBooks(a, b, 'recent')));

    const sortedTitle = [...numBooks].sort((a, b) => compareBooks(a, b, 'title'));
    assert.equal(sortedTitle[0].id, 102); // '1984' идет перед 'Аэлита'
    assert.equal(sortedTitle[1].id, 101);

    const sameBooksNumericId = [
      { id: 102, title: 'Книга', author: 'Автор' },
      { id: 101, title: 'Книга', author: 'Автор' },
    ];
    const sortedById = [...sameBooksNumericId].sort((a, b) => compareBooks(a, b, 'title'));
    assert.equal(sortedById[0].id, 101);
    assert.equal(sortedById[1].id, 102);
  });

  await t.test('compareBooks без третьего аргумента по умолчанию использует режим «recent»', () => {
    const bookNewer = { id: 'b-new', title: 'Новая', added: 2000, year: 2023 };
    const bookOlder = { id: 'b-old', title: 'Старая', added: 1000, year: 2020 };
    const bookSameDateNewerYear = { id: 'b-year-new', title: 'А', added: 1000, year: 2022 };
    const bookSameDateOlderYear = { id: 'b-year-old', title: 'Б', added: 1000, year: 2019 };

    assert.equal(compareBooks(bookNewer, bookOlder), compareBooks(bookNewer, bookOlder, 'recent'));
    assert.ok(compareBooks(bookNewer, bookOlder) < 0);
    assert.ok(compareBooks(bookOlder, bookNewer) > 0);

    // При одинаковом added проверяет сортировку по убыванию года (year desc)
    assert.equal(
      compareBooks(bookSameDateNewerYear, bookSameDateOlderYear),
      compareBooks(bookSameDateNewerYear, bookSameDateOlderYear, 'recent')
    );
    assert.ok(compareBooks(bookSameDateNewerYear, bookSameDateOlderYear) < 0);
    assert.ok(compareBooks(bookSameDateOlderYear, bookSameDateNewerYear) > 0);
  });

  await t.test('тай-брейк по id в режиме «author» для книг без автора и с одинаковыми названиями', () => {
    const bookZ = { id: 'id-z', title: 'Одинаковое название', author: '' };
    const bookA = { id: 'id-a', title: 'Одинаковое название', author: '' };
    const sorted = [bookZ, bookA].sort((a, b) => compareBooks(a, b, 'author'));
    assert.deepEqual(sorted.map((b) => b.id), ['id-a', 'id-z']);

    const bookUndefZ = { id: 'id-z', title: 'То же название', author: undefined };
    const bookUndefA = { id: 'id-a', title: 'То же название', author: undefined };
    const sortedUndef = [bookUndefZ, bookUndefA].sort((a, b) => compareBooks(a, b, 'author'));
    assert.deepEqual(sortedUndef.map((b) => b.id), ['id-a', 'id-z']);
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
    assert.equal(matchesGenre(null, '   '), true);
    assert.equal(matchesGenre(undefined, '   '), true);
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
