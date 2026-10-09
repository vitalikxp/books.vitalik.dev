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
    is_valid_image,
    search_google_books,
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


class TestImageValidation(unittest.TestCase):
    """Tests for is_valid_image magic numbers and HTML rejection."""

    def test_valid_jpeg(self):
        jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
        self.assertTrue(is_valid_image(jpeg_header))

    def test_valid_png(self):
        png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        self.assertTrue(is_valid_image(png_header))

    def test_valid_webp(self):
        webp_header = b"RIFF\x24\x00\x00\x00WEBPVP8 "
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
    def test_search_google_books_empty_results(self, mock_fetch_json):
        mock_fetch_json.return_value = None
        result = search_google_books("Несуществующая книга")
        self.assertIsNone(result)


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


if __name__ == "__main__":
    unittest.main()
