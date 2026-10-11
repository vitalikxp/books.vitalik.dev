#!/usr/bin/env python3
"""
Unit tests for scripts/book_scanner.py
"""

import io
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.book_scanner import (
    add_book,
    clean_description,
    download_image,
    fetch_json,
    is_valid_image,
    main,
    search_google_books,
    search_open_library,
    slugify,
)


class TestSlugify(unittest.TestCase):
    """Tests for slugify function."""

    def test_cyrillic_transliteration(self):
        self.assertEqual(slugify("Мастер и Маргарита"), "master-i-margarita")
        self.assertEqual(slugify("Лев Толстой"), "lev-tolstoy")
        self.assertEqual(slugify("Щегол"), "shchegol")
        self.assertEqual(slugify("Юрий Гагарин"), "yuriy-gagarin")
        self.assertEqual(slugify("Война и мир"), "voyna-i-mir")
        self.assertEqual(slugify("Федор Достоевский"), "fedor-dostoevskiy")

    def test_hard_and_soft_signs(self):
        self.assertEqual(slugify("подъезд"), "podezd")
        self.assertEqual(slugify("мать"), "mat")

    def test_all_cyrillic_letters(self):
        # Pangram testing all Cyrillic characters
        text = "Съешь же ещё этих мягких французских булок"
        expected = "sesh-zhe-eshchyo-etikh-myagkikh-frantsuzskikh-bulok"
        self.assertEqual(slugify(text), expected)

    def test_special_characters_and_punctuation(self):
        self.assertEqual(slugify("C++ & Python: Руководство!"), "c-python-rukovodstvo")
        self.assertEqual(slugify("Hello,  World!  ---  Test___123"), "hello-world-test-123")
        self.assertEqual(slugify("   ---Book Title---   "), "book-title")

    def test_length_limit(self):
        long_title = "Очень длинное название книги, которое обязательно превысит лимит в шестьдесят символов"
        slug = slugify(long_title)
        self.assertLessEqual(len(slug), 60)
        self.assertFalse(slug.endswith("-"))

    def test_empty_and_special_only(self):
        self.assertEqual(slugify(""), "book")
        self.assertEqual(slugify("   "), "book")
        self.assertEqual(slugify("!@#$%^&*()_+{}[]:;<>?,./"), "book")

    def test_slugify_none_input(self):
        self.assertEqual(slugify(None), "book")

    def test_ukrainian_letters_transliteration(self):
        slug = slugify("Сергій Жадан")
        self.assertEqual(slug, "sergiy-zhadan")
        self.assertTrue(slug.isascii())
        self.assertNotIn("і", slug)

    def test_diacritics_transliteration(self):
        slug = slugify("René Descartes")
        self.assertEqual(slug, "rene-descartes")
        self.assertTrue(slug.isascii())

    def test_belarusian_and_ukrainian_extended_characters(self):
        # 'і': 'i', 'ї': 'yi', 'є': 'ye', 'ґ': 'g', 'ў': 'u'
        slug = slugify("Їжак Євген Ґрунт Ўладзімір Сергій")
        self.assertEqual(slug, "yizhak-yevgen-grunt-uladzimir-sergiy")
        self.assertTrue(slug.isascii())


class TestCleanDescription(unittest.TestCase):
    """Tests for clean_description function."""

    def test_paragraph_separation_br(self):
        raw = "Первая строка<br>Вторая строка<br/>Третья строка<br />Четвертая"
        expected = "Первая строка\n\nВторая строка\n\nТретья строка\n\nЧетвертая"
        self.assertEqual(clean_description(raw), expected)

    def test_paragraph_separation_p_and_div(self):
        raw = "<p>Первый абзац</p><p>Второй абзац</p>"
        expected = "Первый абзац\n\nВторой абзац"
        self.assertEqual(clean_description(raw), expected)

        raw_div = "<div>Первый блок</div><div>Второй блок</div>"
        expected_div = "Первый блок\n\nВторой блок"
        self.assertEqual(clean_description(raw_div), expected_div)

    def test_multiple_consecutive_breaks_condensed(self):
        raw = "Абзац 1<br><br><br><br>Абзац 2"
        expected = "Абзац 1\n\nАбзац 2"
        self.assertEqual(clean_description(raw), expected)

    def test_html_entity_decoding(self):
        raw = "&laquo;Война и мир&raquo; &amp; &quot;1984&quot; &#39;test&#39;"
        expected = "«Война и мир» & \"1984\" 'test'"
        self.assertEqual(clean_description(raw), expected)

    def test_other_html_tags_stripped(self):
        raw = "<p>Это <b>жирный</b> текст со <a href='https://example.com'>ссылкой</a> и <i>курсивом</i>.</p>"
        expected = "Это жирный текст со ссылкой и курсивом."
        self.assertEqual(clean_description(raw), expected)

    def test_empty_or_whitespace_input(self):
        self.assertEqual(clean_description(""), "")
        self.assertEqual(clean_description(None), "")
        self.assertEqual(clean_description("<p></p>"), "")
        self.assertEqual(clean_description("<br><br/>"), "")

    def test_block_html_tags_separation(self):
        # Lists
        raw_list = "<ul><li>Пункт 1</li><li>Пункт 2</li></ul>"
        self.assertEqual(clean_description(raw_list), "Пункт 1\n\nПункт 2")

        # Headings and paragraphs
        raw_heading = "<h1>Заголовок</h1><p>Текст</p>"
        self.assertEqual(clean_description(raw_heading), "Заголовок\n\nТекст")

        # Blockquotes, tables, definition lists
        raw_blocks = "<blockquote>Цитата</blockquote><table><tr><td>Ячейка 1</td><td>Ячейка 2</td></tr></table><dl><dt>Термин</dt><dd>Определение</dd></dl>"
        self.assertEqual(clean_description(raw_blocks), "Цитата\n\nЯчейка 1\n\nЯчейка 2\n\nТермин\n\nОпределение")


class TestImageValidation(unittest.TestCase):
    """Tests for is_valid_image magic numbers and HTML rejection."""

    def test_valid_jpeg(self):
        jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 20
        self.assertTrue(is_valid_image(jpeg_header))

    def test_valid_png(self):
        png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20
        self.assertTrue(is_valid_image(png_header))

    def test_valid_webp(self):
        webp_header = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 20
        self.assertTrue(is_valid_image(webp_header))

    def test_reject_html_responses(self):
        html_doc = b"<!DOCTYPE html><html><body>Error 404</body></html>"
        self.assertFalse(is_valid_image(html_doc))

        html_tag = b"<html><head><title>Not Found</title></head></html>"
        self.assertFalse(is_valid_image(html_tag))

        html_whitespace = b"  \r\n\t<!doctype html><html><body>Error</body></html>"
        self.assertFalse(is_valid_image(html_whitespace))

        html_head = b"<head><meta charset='utf-8'></head>"
        self.assertFalse(is_valid_image(html_head))

    def test_reject_empty_and_invalid_data(self):
        self.assertFalse(is_valid_image(b""))
        self.assertFalse(is_valid_image(None))
        self.assertFalse(is_valid_image(b"Plain text error message"))
        self.assertFalse(is_valid_image(b"\x00\x01\x02\x03\x04\x05"))
        # Header shorter than 32 bytes is rejected
        self.assertFalse(is_valid_image(b"\xff\xd8\xff\xe0" + b"\x00" * 10))


class TestFetchJson(unittest.TestCase):
    """Tests for fetch_json function."""

    @patch("urllib.request.urlopen")
    def test_fetch_json_network_failure_returns_none_and_logs(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection timed out")

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = fetch_json("https://example.com/api/test")

        self.assertIsNone(result)
        self.assertIn("Ошибка запроса к https://example.com/api/test", mock_stderr.getvalue())
        self.assertIn("Connection timed out", mock_stderr.getvalue())

    @patch("urllib.request.urlopen")
    def test_fetch_json_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "ok", "items": [1, 2, 3]}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = fetch_json("https://example.com/api/test")
        self.assertEqual(result, {"status": "ok", "items": [1, 2, 3]})


class TestDownloadImage(unittest.TestCase):
    """Tests for download_image atomic writes, error handling, and preservation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dest_path = Path(self.temp_dir.name) / "test_cover.jpg"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("urllib.request.urlopen")
    def test_download_valid_image_success(self, mock_urlopen):
        valid_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 100
        mock_response = MagicMock()
        mock_response.read.return_value = valid_jpeg
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = download_image("https://example.com/cover.jpg", self.dest_path)
        self.assertTrue(result)
        self.assertTrue(self.dest_path.exists())
        self.assertEqual(self.dest_path.read_bytes(), valid_jpeg)

        # Temporary file should not exist
        tmp_path = self.dest_path.with_name(f"{self.dest_path.name}.tmp")
        self.assertFalse(tmp_path.exists())

    @patch("urllib.request.urlopen")
    def test_download_html_response_rejected(self, mock_urlopen):
        html_data = b"<!DOCTYPE html><html><body>Error 404 Not Found</body></html>"
        mock_response = MagicMock()
        mock_response.read.return_value = html_data
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = download_image("https://example.com/cover.jpg", self.dest_path)

        self.assertFalse(result)
        self.assertFalse(self.dest_path.exists())
        self.assertIn("HTML", mock_stderr.getvalue())

    @patch("urllib.request.urlopen")
    def test_download_empty_response_rejected(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = download_image("https://example.com/cover.jpg", self.dest_path)

        self.assertFalse(result)
        self.assertFalse(self.dest_path.exists())
        self.assertIn("Пустой ответ", mock_stderr.getvalue())

    @patch("urllib.request.urlopen")
    def test_existing_file_preserved_on_network_error(self, mock_urlopen):
        # Pre-create the destination file
        initial_data = b"existing_valid_cover_content"
        self.dest_path.write_bytes(initial_data)

        # Simulate network error
        mock_urlopen.side_effect = Exception("Connection timed out")

        with patch("sys.stderr", new_callable=io.StringIO):
            result = download_image("https://example.com/cover.jpg", self.dest_path)

        self.assertFalse(result)
        # CRITICAL: dest_path must NOT be deleted or modified!
        self.assertTrue(self.dest_path.exists())
        self.assertEqual(self.dest_path.read_bytes(), initial_data)

        # Temporary file should not exist
        tmp_path = self.dest_path.with_name(f"{self.dest_path.name}.tmp")
        self.assertFalse(tmp_path.exists())

    @patch("urllib.request.urlopen")
    def test_existing_file_preserved_on_invalid_image(self, mock_urlopen):
        initial_data = b"existing_cover_data"
        self.dest_path.write_bytes(initial_data)

        # Return invalid data (HTML)
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html>404</html>"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch("sys.stderr", new_callable=io.StringIO):
            result = download_image("https://example.com/cover.jpg", self.dest_path)

        self.assertFalse(result)
        self.assertTrue(self.dest_path.exists())
        self.assertEqual(self.dest_path.read_bytes(), initial_data)

    @patch("urllib.request.urlopen")
    def test_atomic_replacement_on_success(self, mock_urlopen):
        # Initial file
        initial_data = b"old_cover_data"
        self.dest_path.write_bytes(initial_data)

        # New valid PNG
        new_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
        mock_response = MagicMock()
        mock_response.read.return_value = new_data
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = download_image("https://example.com/new_cover.png", self.dest_path)
        self.assertTrue(result)
        self.assertTrue(self.dest_path.exists())
        self.assertEqual(self.dest_path.read_bytes(), new_data)

    @patch("urllib.request.urlopen")
    def test_download_non_image_binary_data_rejected(self, mock_urlopen):
        non_image_data = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x10\x11\x12"
        mock_response = MagicMock()
        mock_response.read.return_value = non_image_data
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = download_image("https://example.com/corrupt_data.bin", self.dest_path)

        self.assertFalse(result)
        self.assertFalse(self.dest_path.exists())
        self.assertIn("Некорректный или неподдерживаемый формат изображения", mock_stderr.getvalue())


class TestSearchGoogleBooks(unittest.TestCase):
    """Tests for search_google_books function."""

    @patch("scripts.book_scanner.fetch_json")
    def test_search_google_books_valid_payload(self, mock_fetch_json):
        mock_fetch_json.return_value = {
            "items": [
                {
                    "volumeInfo": {
                        "title": "Мастер и Маргарита",
                        "authors": ["Михаил Булгаков"],
                        "publishedDate": "1967-05-15",
                        "publisher": "Художественная литература",
                        "industryIdentifiers": [
                            {"type": "ISBN_10", "identifier": "1234567890"},
                            {"type": "ISBN_13", "identifier": "9781234567890"},
                        ],
                        "pageCount": 480,
                        "categories": ["Художественная литература"],
                        "language": "ru",
                        "description": "Культовый роман.",
                        "imageLinks": {
                            "thumbnail": "http://books.google.com/books/content?id=xyz&zoom=1&edge=curl"
                        },
                    }
                }
            ]
        }

        result = search_google_books("Мастер и Маргарита")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Мастер и Маргарита")
        self.assertEqual(result["author"], "Михаил Булгаков")
        self.assertEqual(result["year"], 1967)
        self.assertEqual(result["publisher"], "Художественная литература")
        self.assertEqual(result["isbn"], "9781234567890")
        self.assertEqual(result["pages"], 480)
        self.assertEqual(result["genres"], ["Художественная литература"])
        self.assertEqual(result["language"], "ru")
        self.assertEqual(result["description"], "Культовый роман.")
        self.assertEqual(result["cover_url"], "https://books.google.com/books/content?id=xyz&zoom=2")

    @patch("scripts.book_scanner.fetch_json")
    def test_search_google_books_none_fields_payload(self, mock_fetch_json):
        """Verify no TypeError is raised when publishedDate and industryIdentifiers are None."""
        mock_fetch_json.return_value = {
            "items": [
                {
                    "volumeInfo": {
                        "title": "Книга без даты и ISBN",
                        "authors": ["Неизвестный"],
                        "publishedDate": None,
                        "industryIdentifiers": None,
                    }
                }
            ]
        }

        # Should execute cleanly without TypeError
        result = search_google_books("Книга без даты и ISBN")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Книга без даты и ISBN")
        self.assertEqual(result["author"], "Неизвестный")
        self.assertIsNone(result["year"])
        self.assertEqual(result["isbn"], "")
        self.assertIsNone(result["cover_url"])
        self.assertEqual(result["genres"], [])

    @patch("scripts.book_scanner.fetch_json")
    def test_search_google_books_none_volume_info_payload(self, mock_fetch_json):
        """Verify no AttributeError is raised when item['volumeInfo'] is None."""
        mock_fetch_json.return_value = {
            "items": [
                {
                    "volumeInfo": None
                }
            ]
        }
        result = search_google_books("Книга с None volumeInfo")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "")
        self.assertEqual(result["author"], "Неизвестный автор")
        self.assertIsNone(result["year"])
        self.assertEqual(result["publisher"], "")
        self.assertEqual(result["isbn"], "")
        self.assertIsNone(result["pages"])
        self.assertEqual(result["genres"], [])
        self.assertEqual(result["language"], "ru")
        self.assertEqual(result["description"], "")
        self.assertIsNone(result["cover_url"])

    @patch("scripts.book_scanner.fetch_json")
    def test_search_google_books_empty_results(self, mock_fetch_json):
        mock_fetch_json.return_value = None
        result = search_google_books("Несуществующая книга")
        self.assertIsNone(result)

    @patch("scripts.book_scanner.fetch_json")
    def test_search_google_books_isbn_cleaning(self, mock_fetch_json):
        mock_fetch_json.return_value = {"items": [{"volumeInfo": {"title": "Test"}}]}
        # Typographical en-dash (\u2013) and "ISBN: " prefix
        search_google_books("ignored query", isbn="ISBN: 978–5–4461–0960–9")
        mock_fetch_json.assert_called_with(
            "https://www.googleapis.com/books/v1/volumes?q=isbn%3A9785446109609&maxResults=3&langRestrict=ru"
        )

        # Typographical em-dash (\u2014) and lowercase "isbn:" prefix
        search_google_books("", isbn="isbn: 978—123—456")
        mock_fetch_json.assert_called_with(
            "https://www.googleapis.com/books/v1/volumes?q=isbn%3A978123456&maxResults=3&langRestrict=ru"
        )

        # Mathematical minus sign (\u2212)
        search_google_books("", isbn="978−5−04−110057−5")
        mock_fetch_json.assert_called_with(
            "https://www.googleapis.com/books/v1/volumes?q=isbn%3A9785041100575&maxResults=3&langRestrict=ru"
        )

        # ISBN-13: and ISBN-10: prefixes
        search_google_books("", isbn="ISBN-13: 978-5-04-110057-5")
        mock_fetch_json.assert_called_with(
            "https://www.googleapis.com/books/v1/volumes?q=isbn%3A9785041100575&maxResults=3&langRestrict=ru"
        )

        search_google_books("", isbn="ISBN-10: 5-04-110057-5")
        mock_fetch_json.assert_called_with(
            "https://www.googleapis.com/books/v1/volumes?q=isbn%3A5041100575&maxResults=3&langRestrict=ru"
        )

        # ISBN 13: and ISBN 10: prefixes (with space)
        search_google_books("", isbn="ISBN 13: 978-5-04-110057-5")
        mock_fetch_json.assert_called_with(
            "https://www.googleapis.com/books/v1/volumes?q=isbn%3A9785041100575&maxResults=3&langRestrict=ru"
        )

        search_google_books("", isbn="ISBN 10: 5-04-110057-5")
        mock_fetch_json.assert_called_with(
            "https://www.googleapis.com/books/v1/volumes?q=isbn%3A5041100575&maxResults=3&langRestrict=ru"
        )

    @patch("scripts.book_scanner.fetch_json")
    def test_search_google_books_language_fallback(self, mock_fetch_json):
        valid_item_payload = {
            "items": [
                {
                    "volumeInfo": {
                        "title": "Designing Data-Intensive Applications",
                        "authors": ["Martin Kleppmann"],
                        "publishedDate": "2017-03-16",
                        "publisher": "O'Reilly Media",
                        "industryIdentifiers": [
                            {"type": "ISBN_13", "identifier": "9781449373320"}
                        ],
                        "pageCount": 616,
                        "categories": ["Computers"],
                        "language": "en",
                        "description": "The big ideas behind reliable systems.",
                    }
                }
            ]
        }
        # First call with langRestrict=ru returns empty items, second call returns valid payload
        mock_fetch_json.side_effect = [{"items": []}, valid_item_payload]

        result = search_google_books("Designing Data-Intensive Applications")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Designing Data-Intensive Applications")
        self.assertEqual(result["author"], "Martin Kleppmann")
        self.assertEqual(result["year"], 2017)
        self.assertEqual(result["isbn"], "9781449373320")
        self.assertEqual(result["language"], "en")
        self.assertEqual(mock_fetch_json.call_count, 2)

    @patch("scripts.book_scanner.fetch_json")
    def test_search_google_books_error_does_not_retry(self, mock_fetch_json):
        mock_fetch_json.return_value = None
        result = search_google_books("Война и мир")
        self.assertIsNone(result)
        self.assertEqual(mock_fetch_json.call_count, 1)


class TestSearchOpenLibrary(unittest.TestCase):
    """Tests for search_open_library function."""

    @patch("scripts.book_scanner.fetch_json")
    def test_search_open_library_isbn_cleaning(self, mock_fetch_json):
        mock_fetch_json.return_value = {"docs": []}
        # Typographical en-dash (\u2013) and "ISBN: " prefix
        search_open_library("ignored query", isbn="ISBN: 978–5–4461–0960–9")
        mock_fetch_json.assert_called_with(
            "https://openlibrary.org/search.json?q=9785446109609&limit=3"
        )

        # Typographical em-dash (\u2014) and lowercase "isbn: " prefix
        search_open_library("", isbn="isbn: 978—123—456")
        mock_fetch_json.assert_called_with(
            "https://openlibrary.org/search.json?q=978123456&limit=3"
        )

        # Mathematical minus sign (\u2212)
        search_open_library("", isbn="978−5−04−110057−5")
        mock_fetch_json.assert_called_with(
            "https://openlibrary.org/search.json?q=9785041100575&limit=3"
        )

        # ISBN-13: and ISBN-10: prefixes
        search_open_library("", isbn="ISBN-13: 978-5-04-110057-5")
        mock_fetch_json.assert_called_with(
            "https://openlibrary.org/search.json?q=9785041100575&limit=3"
        )

        search_open_library("", isbn="ISBN-10: 5-04-110057-5")
        mock_fetch_json.assert_called_with(
            "https://openlibrary.org/search.json?q=5041100575&limit=3"
        )

        # ISBN 13: and ISBN 10: prefixes (with space)
        search_open_library("", isbn="ISBN 13: 978-5-04-110057-5")
        mock_fetch_json.assert_called_with(
            "https://openlibrary.org/search.json?q=9785041100575&limit=3"
        )

        search_open_library("", isbn="ISBN 10: 5-04-110057-5")
        mock_fetch_json.assert_called_with(
            "https://openlibrary.org/search.json?q=5041100575&limit=3"
        )

    @patch("scripts.book_scanner.fetch_json")
    def test_search_open_library_valid_payload(self, mock_fetch_json):
        mock_fetch_json.return_value = {
            "docs": [
                {
                    "title": "Преступление и наказание",
                    "author_name": ["Фёдор Достоевский"],
                    "first_publish_year": 1866,
                    "publisher": ["Русский вестник"],
                    "isbn": ["9785171123456"],
                    "number_of_pages_median": 672,
                    "subject": ["Классика", "Роман"],
                    "language": ["rus"],
                    "cover_i": 123456,
                }
            ]
        }
        result = search_open_library("Преступление и наказание")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Преступление и наказание")
        self.assertEqual(result["author"], "Фёдор Достоевский")
        self.assertEqual(result["year"], 1866)
        self.assertEqual(result["publisher"], "Русский вестник")
        self.assertEqual(result["isbn"], "9785171123456")
        self.assertEqual(result["pages"], 672)
        self.assertEqual(result["cover_url"], "https://covers.openlibrary.org/b/id/123456-L.jpg")

    @patch("scripts.book_scanner.fetch_json")
    def test_search_open_library_empty_docs_returns_none(self, mock_fetch_json):
        mock_fetch_json.return_value = {"docs": []}
        result = search_open_library("Несуществующая книга")
        self.assertIsNone(result)

    @patch("scripts.book_scanner.fetch_json")
    def test_search_open_library_non_russian_language(self, mock_fetch_json):
        mock_fetch_json.return_value = {
            "docs": [
                {
                    "title": "Clean Architecture",
                    "author_name": ["Robert C. Martin"],
                    "first_publish_year": 2017,
                    "publisher": ["Prentice Hall"],
                    "isbn": ["9780134494166"],
                    "number_of_pages_median": 432,
                    "subject": ["Software"],
                    "language": ["eng"],
                    "cover_i": 654321,
                }
            ]
        }
        result = search_open_library("Clean Architecture")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Clean Architecture")
        self.assertEqual(result["author"], "Robert C. Martin")
        self.assertEqual(result["language"], "eng")

    @patch("scripts.book_scanner.fetch_json")
    def test_search_open_library_handles_non_string_authors(self, mock_fetch_json):
        mock_fetch_json.return_value = {
            "docs": [
                {
                    "title": "Книга со смешанными авторами",
                    "author_name": ["Author", None, 123, ""],
                }
            ]
        }
        result = search_open_library("Тест")
        self.assertIsNotNone(result)
        self.assertEqual(result["author"], "Author, 123")

        # Test case where author_name contains only None or empty strings
        mock_fetch_json.return_value = {
            "docs": [
                {
                    "title": "Книга без валидных авторов",
                    "author_name": [None, ""],
                }
            ]
        }
        result_empty = search_open_library("Тест 2")
        self.assertIsNotNone(result_empty)
        self.assertEqual(result_empty["author"], "Неизвестный автор")


class TestAddBook(unittest.TestCase):
    """Tests for add_book function."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)
        self.books_dir = self.root_dir / "src" / "content" / "books"
        self.covers_dir = self.root_dir / "public" / "covers"
        self.incoming_dir = self.root_dir / "incoming_photos"
        self.processed_dir = self.root_dir / "processed_photos"

        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.covers_dir.mkdir(parents=True, exist_ok=True)
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        self.patchers = [
            patch("scripts.book_scanner.ROOT_DIR", self.root_dir),
            patch("scripts.book_scanner.BOOKS_DIR", self.books_dir),
            patch("scripts.book_scanner.COVERS_DIR", self.covers_dir),
            patch("scripts.book_scanner.INCOMING_DIR", self.incoming_dir),
            patch("scripts.book_scanner.PROCESSED_DIR", self.processed_dir),
            patch("scripts.book_scanner.fetch_json", return_value=None),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.temp_dir.cleanup()

    @patch("scripts.book_scanner.download_image")
    def test_add_book_with_mocked_cover_download_and_schema_validation(self, mock_download):
        mock_download.return_value = True

        success = add_book(
            title="Чистый код",
            author="Роберт Мартин",
            isbn="978-5-4461-0960-9",
            year=2019,
            publisher="Питер",
            pages=464,
            genres=["Программирование", "Разработка"],
            description="Руководство по созданию чистого кода.",
            status="read",
            rating=5,
            custom_cover="https://example.com/clean-code.jpg",
        )

        self.assertTrue(success)
        expected_md = self.books_dir / "robert-martin-chistyy-kod.md"
        self.assertTrue(expected_md.exists())

        mock_download.assert_called_once_with(
            "https://example.com/clean-code.jpg",
            self.covers_dir / "robert-martin-chistyy-kod.jpg",
        )

        # Parse YAML frontmatter and verify against Astro content schema (src/content.config.ts)
        raw = expected_md.read_text(encoding="utf-8")
        parts = raw.split("---")
        self.assertGreaterEqual(len(parts), 3)
        fm = yaml.safe_load(parts[1])
        body = "---".join(parts[2:]).strip()

        # Schema checks
        self.assertIsInstance(fm["title"], str)
        self.assertEqual(fm["title"], "Чистый код")
        self.assertIsInstance(fm["author"], str)
        self.assertEqual(fm["author"], "Роберт Мартин")
        self.assertIsInstance(fm["year"], int)
        self.assertEqual(fm["year"], 2019)
        self.assertIsInstance(fm["publisher"], str)
        self.assertEqual(fm["publisher"], "Питер")
        self.assertIsInstance(fm["isbn"], str)
        self.assertEqual(fm["isbn"], "978-5-4461-0960-9")
        self.assertEqual(fm["language"], "ru")
        self.assertIsInstance(fm["pages"], int)
        self.assertEqual(fm["pages"], 464)
        self.assertEqual(fm["cover"], "/covers/robert-martin-chistyy-kod.jpg")
        self.assertIsInstance(fm["genres"], list)
        self.assertEqual(fm["genres"], ["Программирование", "Разработка"])
        self.assertIn(fm["status"], ["read", "reading", "to-read", "planned", "neutral"])
        self.assertEqual(fm["status"], "read")
        self.assertIsInstance(fm["rating"], int)
        self.assertEqual(fm["rating"], 5)
        self.assertTrue(1 <= fm["rating"] <= 5)
        self.assertIn("addedAt", fm)
        self.assertTrue(isinstance(fm["addedAt"], (date, str)))
        self.assertEqual(body, "Руководство по созданию чистого кода.")

    def test_add_book_with_local_cover(self):
        success = add_book(
            title="Локальная книга",
            author="Тестовый автор",
            year=2022,
            custom_cover="/covers/custom-cover.jpg",
        )
        self.assertTrue(success)
        expected_md = self.books_dir / "testovyy-avtor-lokalnaya-kniga.md"
        self.assertTrue(expected_md.exists())

        raw = expected_md.read_text(encoding="utf-8")
        parts = raw.split("---")
        fm = yaml.safe_load(parts[1])
        self.assertEqual(fm["cover"], "/covers/custom-cover.jpg")

    def test_add_book_photo_relocation_incoming_to_processed(self):
        photo_filename = "photo_incoming.jpg"
        photo_content = b"incoming_jpeg_binary_data_12345"
        incoming_file = self.incoming_dir / photo_filename
        incoming_file.write_bytes(photo_content)

        success = add_book(
            title="Книга с фото",
            author="Фото Автор",
            photo_path=photo_filename,
            year=2023,
            custom_cover="/covers/default-book.svg",
        )
        self.assertTrue(success)

        # File moved from incoming_photos to processed_photos
        self.assertFalse(incoming_file.exists())
        processed_file = self.processed_dir / photo_filename
        self.assertTrue(processed_file.exists())
        # Original photo preserved intact (not deleted)
        self.assertEqual(processed_file.read_bytes(), photo_content)

    def test_add_book_photo_collision_preserves_both_files(self):
        photo_filename = "duplicate.jpg"
        existing_content = b"existing_photo_content"
        new_content = b"new_incoming_photo_content"

        existing_file = self.processed_dir / photo_filename
        existing_file.write_bytes(existing_content)

        incoming_file = self.incoming_dir / photo_filename
        incoming_file.write_bytes(new_content)

        success = add_book(
            title="Вторая книга",
            author="Автор",
            photo_path=photo_filename,
            year=2023,
            custom_cover="/covers/default-book.svg",
        )
        self.assertTrue(success)

        # Incoming file moved
        self.assertFalse(incoming_file.exists())
        # Both photos preserved in processed_photos without deletion
        self.assertTrue(existing_file.exists())
        self.assertEqual(existing_file.read_bytes(), existing_content)

        renamed_file = self.processed_dir / "duplicate_1.jpg"
        self.assertTrue(renamed_file.exists())
        self.assertEqual(renamed_file.read_bytes(), new_content)

    @patch("scripts.book_scanner.search_google_books")
    def test_add_book_whitespace_query_fallback(self, mock_search):
        # Query with only whitespace should be stripped and fallback to author + title
        mock_search.return_value = {
            "title": "Война и мир",
            "author": "Лев Толстой",
            "year": 1869,
            "publisher": "Типография",
            "isbn": "9785389062566",
            "pages": 1300,
            "genres": ["Классика"],
            "language": "ru",
            "description": "Роман-эпопея.",
            "cover_url": None,
        }

        success = add_book(
            query="   ",
            title="Война и мир",
            author="Лев Толстой",
        )
        self.assertTrue(success)
        mock_search.assert_called_once_with("Лев Толстой Война и мир", isbn="")
        expected_md = self.books_dir / "lev-tolstoy-voyna-i-mir.md"
        self.assertTrue(expected_md.exists())

    def test_add_book_collision_without_force_fails_and_preserves_file(self):
        slug_md = self.books_dir / "testovyy-avtor-testovaya-kniga.md"
        original_content = "--- title: Original ---"
        slug_md.write_text(original_content, encoding="utf-8")

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = add_book(
                title="Тестовая книга",
                author="Тестовый автор",
                year=2024,
                custom_cover="/covers/default-book.svg",
                force=False,
            )

        self.assertFalse(result)
        self.assertTrue(slug_md.exists())
        self.assertEqual(slug_md.read_text(encoding="utf-8"), original_content)
        self.assertIn("уже существует", mock_stderr.getvalue())

    def test_add_book_collision_with_force_overwrites(self):
        slug_md = self.books_dir / "testovyy-avtor-testovaya-kniga.md"
        original_content = "--- title: Original ---"
        slug_md.write_text(original_content, encoding="utf-8")

        result = add_book(
            title="Тестовая книга",
            author="Тестовый автор",
            description="Обновленное описание книги",
            year=2024,
            custom_cover="/covers/default-book.svg",
            force=True,
        )

        self.assertTrue(result)
        self.assertTrue(slug_md.exists())
        updated_content = slug_md.read_text(encoding="utf-8")
        self.assertNotEqual(updated_content, original_content)
        self.assertIn("Обновленное описание книги", updated_content)

    @patch("scripts.book_scanner.search_google_books")
    def test_add_book_api_none_title_falls_back_to_search_query(self, mock_search):
        mock_search.return_value = {
            "title": None,
            "author": None,
            "year": 2021,
            "publisher": "Издательство",
            "isbn": "9781234567890",
            "pages": 200,
            "genres": ["Тест"],
            "language": "ru",
            "description": "Тестовое описание",
            "cover_url": None,
        }

        # Query provided -> title falls back to search_q ("Поисковая книга"), author to 'Неизвестный автор'
        success = add_book(query="Поисковая книга", force=True)
        self.assertTrue(success)
        expected_md = self.books_dir / "neizvestnyy-avtor-poiskovaya-kniga.md"
        self.assertTrue(expected_md.exists())

        raw = expected_md.read_text(encoding="utf-8")
        parts = raw.split("---")
        self.assertGreaterEqual(len(parts), 3)
        fm = yaml.safe_load(parts[1])
        self.assertEqual(fm["title"], "Поисковая книга")
        self.assertEqual(fm["author"], "Неизвестный автор")
        self.assertIsNotNone(fm["title"])
        self.assertIsNotNone(fm["author"])
        self.assertNotEqual(fm["title"], "")
        self.assertNotEqual(fm["author"], "")

    @patch("scripts.book_scanner.search_google_books")
    def test_add_book_api_none_title_falls_back_to_default_title(self, mock_search):
        mock_search.return_value = {
            "title": None,
            "author": None,
            "year": 2021,
            "publisher": "Издательство",
            "isbn": "9781234567890",
            "pages": 200,
            "genres": ["Тест"],
            "language": "ru",
            "description": "Тестовое описание",
            "cover_url": None,
        }

        # Search by ISBN with empty title/author -> title falls back to 'Без названия', author to 'Неизвестный автор'
        success = add_book(isbn="9781234567890", force=True)
        self.assertTrue(success)
        expected_md = self.books_dir / "neizvestnyy-avtor-bez-nazvaniya.md"
        self.assertTrue(expected_md.exists())

        raw = expected_md.read_text(encoding="utf-8")
        parts = raw.split("---")
        self.assertGreaterEqual(len(parts), 3)
        fm = yaml.safe_load(parts[1])
        self.assertEqual(fm["title"], "Без названия")
        self.assertEqual(fm["author"], "Неизвестный автор")
        self.assertIsNotNone(fm["title"])
        self.assertIsNotNone(fm["author"])
        self.assertNotEqual(fm["title"], "")
        self.assertNotEqual(fm["author"], "")

    def test_add_book_photo_directory_rejected(self):
        dir_name = "test_photos_dir"
        fake_dir = self.incoming_dir / dir_name
        fake_dir.mkdir()

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            success = add_book(
                title="Книга с директорией",
                author="Автор",
                photo_path=dir_name,
                year=2024,
                custom_cover="/covers/default-book.svg",
            )

        self.assertTrue(success)
        # Directory should NOT be moved into processed_photos
        self.assertTrue(fake_dir.exists())
        self.assertTrue(fake_dir.is_dir())
        self.assertFalse((self.processed_dir / dir_name).exists())
        self.assertIn("не является файлом фотографии", mock_stderr.getvalue())

    @patch("scripts.book_scanner.download_image", return_value=False)
    def test_add_book_failed_cover_download_fallback(self, mock_download):
        success = add_book(
            title="Книга со сбойной обложкой",
            author="Автор",
            year=2023,
            custom_cover="https://example.com/broken-cover.jpg",
        )
        self.assertTrue(success)
        expected_md = self.books_dir / "avtor-kniga-so-sboynoy-oblozhkoy.md"
        self.assertTrue(expected_md.exists())

        raw = expected_md.read_text(encoding="utf-8")
        parts = raw.split("---")
        fm = yaml.safe_load(parts[1])
        self.assertEqual(fm["cover"], "/covers/default-book.svg")

    @patch("scripts.book_scanner.search_google_books")
    def test_add_book_language_none_fallback_to_ru(self, mock_search):
        mock_search.return_value = {
            "title": "Книга без языка",
            "author": "Автор",
            "year": 2024,
            "publisher": "Издательство",
            "isbn": "9781234567890",
            "pages": 100,
            "genres": ["Тест"],
            "language": None,
            "description": "Описание",
            "cover_url": None,
        }

        success = add_book(query="Книга без языка", force=True)
        self.assertTrue(success)
        expected_md = self.books_dir / "avtor-kniga-bez-yazyka.md"
        self.assertTrue(expected_md.exists())

        raw = expected_md.read_text(encoding="utf-8")
        parts = raw.split("---")
        fm = yaml.safe_load(parts[1])
        self.assertEqual(fm["language"], "ru")

    def test_add_book_atomic_write_and_nonexistent_books_dir(self):
        import shutil
        if self.books_dir.exists():
            shutil.rmtree(self.books_dir)
        self.assertFalse(self.books_dir.exists())

        success = add_book(
            title="Новая книга в новой директории",
            author="Автор",
            year=2024,
            custom_cover="/covers/default-book.svg",
        )
        self.assertTrue(success)
        self.assertTrue(self.books_dir.exists())
        expected_md = self.books_dir / "avtor-novaya-kniga-v-novoy-direktorii.md"
        self.assertTrue(expected_md.exists())

        # Temporary .tmp file should not remain after atomic replace
        tmp_md = expected_md.with_name(f"{expected_md.name}.tmp")
        self.assertFalse(tmp_md.exists())

        raw = expected_md.read_text(encoding="utf-8")
        parts = raw.split("---")
        fm = yaml.safe_load(parts[1])
        self.assertEqual(fm["title"], "Новая книга в новой директории")

    @patch("scripts.book_scanner.search_open_library")
    @patch("scripts.book_scanner.search_google_books")
    def test_add_book_open_library_fallback_integration(self, mock_google, mock_openlib):
        mock_google.return_value = None
        mock_openlib.return_value = {
            "title": "Open Library Book",
            "author": "Open Library Author",
            "year": 2020,
            "publisher": "Open Publisher",
            "isbn": "9781111111111",
            "pages": 350,
            "genres": ["Testing"],
            "language": "en",
            "description": "Found via Open Library fallback.",
            "cover_url": None,
        }

        success = add_book(query="Test Book", force=True)
        self.assertTrue(success)
        mock_google.assert_called_once_with("Test Book", isbn="")
        mock_openlib.assert_called_once_with("Test Book", isbn="")

        expected_md = self.books_dir / "open-library-author-open-library-book.md"
        self.assertTrue(expected_md.exists())
        raw = expected_md.read_text(encoding="utf-8")
        parts = raw.split("---")
        self.assertGreaterEqual(len(parts), 3)
        fm = yaml.safe_load(parts[1])
        self.assertEqual(fm["title"], "Open Library Book")
        self.assertEqual(fm["author"], "Open Library Author")
        self.assertEqual(fm["year"], 2020)
        self.assertEqual(fm["publisher"], "Open Publisher")
        self.assertEqual(fm["isbn"], "9781111111111")
        self.assertEqual(fm["language"], "en")
        body = "---".join(parts[2:]).strip()
        self.assertEqual(body, "Found via Open Library fallback.")

    def test_add_book_photo_already_in_processed_dir(self):
        photo_filename = "already_processed.jpg"
        photo_content = b"already_processed_photo_data"
        processed_photo = self.processed_dir / photo_filename
        processed_photo.write_bytes(photo_content)

        success = add_book(
            title="Книга с уже обработанным фото",
            author="Автор",
            photo_path=str(processed_photo),
            year=2024,
            custom_cover="/covers/default-book.svg",
        )
        self.assertTrue(success)
        self.assertTrue(processed_photo.exists())
        self.assertEqual(processed_photo.read_bytes(), photo_content)

        # No duplicate counter files created in processed_photos
        counter_file = self.processed_dir / f"{processed_photo.stem}_1{processed_photo.suffix}"
        self.assertFalse(counter_file.exists())
        files_in_processed = list(self.processed_dir.iterdir())
        self.assertEqual(files_in_processed, [processed_photo])

    def test_add_book_nonexistent_photo_warns_and_proceeds(self):
        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            success = add_book(
                title="Книга с несуществующим фото",
                author="Автор",
                photo_path="nonexistent_photo_123.jpg",
                year=2024,
                custom_cover="/covers/default-book.svg",
            )
        self.assertTrue(success)
        expected_md = self.books_dir / "avtor-kniga-s-nesushchestvuyushchim-foto.md"
        self.assertTrue(expected_md.exists())
        self.assertIn("не найден", mock_stderr.getvalue())

    def test_add_book_empty_query_and_isbn_returns_false(self):
        result = add_book()
        self.assertFalse(result)
        self.assertEqual(list(self.books_dir.glob("*.md")), [])

    @patch("scripts.book_scanner.download_image", return_value=True)
    @patch("scripts.book_scanner.search_google_books")
    def test_add_book_explicit_args_override_api_metadata(self, mock_search, mock_download):
        mock_search.return_value = {
            "title": "API Название",
            "author": "API Автор",
            "year": 1999,
            "publisher": "API Издательство",
            "isbn": "9780000000000",
            "pages": 150,
            "genres": ["API Жанр"],
            "language": "ru",
            "description": "API Описание",
            "cover_url": "https://example.com/api-cover.jpg",
        }
        success = add_book(
            query="API Название",
            title="Явное Название",
            author="Явный Автор",
            isbn="978-5-04-110057-5",
            year=2024,
            publisher="Явное Издательство",
            pages=320,
            genres=["Явный Жанр"],
            description="Явное описание",
            custom_cover="https://example.com/custom-cover.jpg",
        )
        self.assertTrue(success)
        expected_md = self.books_dir / "yavnyy-avtor-yavnoe-nazvanie.md"
        self.assertTrue(expected_md.exists())

        raw = expected_md.read_text(encoding="utf-8")
        parts = raw.split("---")
        fm = yaml.safe_load(parts[1])
        body = "---".join(parts[2:]).strip()

        self.assertEqual(fm["title"], "Явное Название")
        self.assertEqual(fm["author"], "Явный Автор")
        self.assertEqual(fm["isbn"], "978-5-04-110057-5")
        self.assertEqual(fm["year"], 2024)
        self.assertEqual(fm["publisher"], "Явное Издательство")
        self.assertEqual(fm["pages"], 320)
        self.assertEqual(fm["genres"], ["Явный Жанр"])
        self.assertEqual(fm["cover"], "/covers/yavnyy-avtor-yavnoe-nazvanie.jpg")
        self.assertEqual(body, "Явное описание")
        mock_download.assert_called_once_with(
            "https://example.com/custom-cover.jpg",
            self.covers_dir / "yavnyy-avtor-yavnoe-nazvanie.jpg",
        )


class TestCLI(unittest.TestCase):
    """Tests for CLI arguments and execution in main()."""

    @patch("scripts.book_scanner.add_book", return_value=True)
    def test_cli_force_argument_handling(self, mock_add_book):
        with patch.object(sys, "argv", ["book_scanner.py", "-t", "Тест", "-a", "Автор", "--force"]):
            main()
        self.assertTrue(mock_add_book.call_args[1]["force"])

        with patch.object(sys, "argv", ["book_scanner.py", "-t", "Тест", "-a", "Автор", "-f"]):
            main()
        self.assertTrue(mock_add_book.call_args[1]["force"])

        with patch.object(sys, "argv", ["book_scanner.py", "-t", "Тест", "-a", "Автор"]):
            main()
        self.assertFalse(mock_add_book.call_args[1]["force"])

    def test_cli_missing_search_target_exits_with_code_1(self):
        with patch.object(sys, "argv", ["book_scanner.py"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as cm:
                    main()
            self.assertEqual(cm.exception.code, 1)

    @patch("scripts.book_scanner.add_book", return_value=False)
    def test_cli_add_book_failure_exits_with_code_1(self, mock_add_book):
        with patch.object(sys, "argv", ["book_scanner.py", "-t", "Test", "-a", "Author"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
