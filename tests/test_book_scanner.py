#!/usr/bin/env python3
"""
Unit tests for scripts/book_scanner.py
"""

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.book_scanner import (
    clean_description,
    download_image,
    is_valid_image,
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


if __name__ == "__main__":
    unittest.main()
