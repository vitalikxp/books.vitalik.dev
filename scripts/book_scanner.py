#!/usr/bin/env python3
"""
Book Scanner & Metadata Fetcher for books.vitalik.dev
Searches Google Books & Open Library for metadata and high-res covers,
then creates a markdown entry and saves the cover image.
"""

import argparse
import html
import json
import os
import re
import shutil
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
COVERS_DIR = ROOT_DIR / "public" / "covers"
BOOKS_DIR = ROOT_DIR / "src" / "content" / "books"
INCOMING_DIR = ROOT_DIR / "incoming_photos"
PROCESSED_DIR = ROOT_DIR / "processed_photos"

# Transliteration dictionary for Cyrillic to slug
TRANSLIT_DICT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'і': 'i', 'ї': 'yi', 'є': 'ye', 'ґ': 'g', 'ў': 'u'
}

def slugify(text: str) -> str:
    text = (text or '').lower().strip()
    res = []
    for char in text:
        if char in TRANSLIT_DICT:
            res.append(TRANSLIT_DICT[char])
        else:
            res.append(char)
    text = ''.join(res)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))

    res = []
    for char in text:
        if ('a' <= char <= 'z') or ('0' <= char <= '9') or char in ['-', ' ']:
            res.append(char)
        else:
            res.append(' ')
    slug = re.sub(r'[-\s_]+', '-', ''.join(res)).strip('-')
    final_slug = slug[:60].rstrip('-')
    return final_slug if final_slug else "book"

def fetch_json(url: str):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"[!] Ошибка запроса к {url}: {e}", file=sys.stderr)
        return None

def is_valid_image(data: bytes) -> bool:
    if not data or len(data) < 32:
        return False
    stripped = data.lstrip()
    if stripped.startswith(b'<') or stripped.lower().startswith(b'<!doctype'):
        return False
    if data.startswith(b'\xff\xd8\xff'):  # JPEG
        return True
    if data.startswith(b'\x89PNG\r\n\x1a\n'):  # PNG
        return True
    if data.startswith(b'RIFF') and b'WEBP' in data[:16]:  # WebP
        return True
    return False

def clean_description(desc: str) -> str:
    if not desc:
        return ""
    desc = re.sub(r'<(?:br\s*/?|/p|/div|/li|/h[1-6]|/blockquote|/tr|/td|/dd|/dt)>', '\n\n', desc, flags=re.IGNORECASE)
    desc = html.unescape(re.sub(r'<[^>]+>', '', desc)).strip()
    desc = re.sub(r'\n{3,}', '\n\n', desc)
    return desc

def download_image(url: str, dest_path: Path) -> bool:
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    tmp_path = dest_path.with_name(f"{dest_path.name}.tmp")
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            if not data or len(data) == 0:
                print(f"[!] Пустой ответ сервера при скачивании обложки {url}", file=sys.stderr)
                return False

            stripped = data.lstrip()
            if stripped.startswith(b'<') or stripped.lower().startswith(b'<!doctype'):
                print(f"[!] Ответ сервера содержит HTML вместо изображения: {url}", file=sys.stderr)
                return False

            if not is_valid_image(data):
                print(f"[!] Некорректный или неподдерживаемый формат изображения: {url}", file=sys.stderr)
                return False

            with open(tmp_path, 'wb') as f:
                f.write(data)

        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            tmp_path.replace(dest_path)
            return True
        else:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            return False
    except Exception as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        print(f"[!] Не удалось скачать обложку {url}: {e}", file=sys.stderr)
        return False

def search_google_books(query: str, isbn: str = None):
    clean_isbn = re.sub(r'(?i)^isbn(?:[-\s]?1[03])?[:\s]*|[-\s\u2010-\u2015\u2212]', '', isbn or '')
    q = f"isbn:{clean_isbn}" if clean_isbn else query
    encoded_q = urllib.parse.quote(q)
    url = f"https://www.googleapis.com/books/v1/volumes?q={encoded_q}&maxResults=3&langRestrict=ru"
    data = fetch_json(url)

    # If request succeeded but no items found in Russian, search without language restriction
    if data and not data.get('items'):
        url = f"https://www.googleapis.com/books/v1/volumes?q={encoded_q}&maxResults=3"
        data = fetch_json(url)

    if not data or not data.get('items'):
        return None

    item = data['items'][0]
    info = item.get('volumeInfo') or {}

    # Extract ISBN
    found_isbn = ""
    for id_info in (info.get('industryIdentifiers') or []):
        if id_info.get('type') in ['ISBN_13', 'ISBN_10']:
            found_isbn = id_info.get('identifier', '')
            if id_info.get('type') == 'ISBN_13':
                break

    # Extract cover URL
    image_links = info.get('imageLinks') or {}
    cover_url = image_links.get('extraLarge') or image_links.get('large') or image_links.get('medium') or image_links.get('thumbnail') or image_links.get('smallThumbnail')
    if cover_url:
        cover_url = cover_url.replace('http://', 'https://')
        cover_url = re.sub(r'&edge=curl', '', cover_url)
        # Attempt to upgrade zoom if possible
        cover_url = re.sub(r'&zoom=\d', '&zoom=2', cover_url)

    published_date = info.get('publishedDate') or ''
    year_match = re.search(r'\d{4}', published_date)
    year = int(year_match.group(0)) if year_match else None

    authors = info.get('authors', [])
    author_str = ", ".join(authors) if authors else "Неизвестный автор"

    return {
        'title': info.get('title', ''),
        'author': author_str,
        'year': year,
        'publisher': info.get('publisher', ''),
        'isbn': found_isbn or (isbn or ''),
        'pages': info.get('pageCount'),
        'genres': info.get('categories', []),
        'language': info.get('language', 'ru'),
        'description': info.get('description', ''),
        'cover_url': cover_url,
    }

def search_open_library(query: str, isbn: str = None):
    clean_isbn = re.sub(r'(?i)^isbn(?:[-\s]?1[03])?[:\s]*|[-\s\u2010-\u2015\u2212]', '', isbn or '')
    q = clean_isbn if clean_isbn else query
    encoded_q = urllib.parse.quote(q)
    url = f"https://openlibrary.org/search.json?q={encoded_q}&limit=3"
    data = fetch_json(url)

    if not data or not data.get('docs'):
        return None

    doc = data['docs'][0]
    cover_i = doc.get('cover_i')
    cover_url = f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg" if cover_i else None

    raw_lang = (doc.get('language') or ['ru'])[0] if doc.get('language') else 'ru'
    lang = 'ru' if raw_lang in ['rus', 'ru'] else raw_lang

    return {
        'title': doc.get('title', ''),
        'author': ", ".join(str(a) for a in (doc.get('author_name') or []) if a) or "Неизвестный автор",
        'year': doc.get('first_publish_year'),
        'publisher': (doc.get('publisher') or [''])[0] if doc.get('publisher') else '',
        'isbn': (doc.get('isbn') or [''])[0] if doc.get('isbn') else '',
        'pages': doc.get('number_of_pages_median'),
        'genres': (doc.get('subject') or [])[:5],
        'language': lang,
        'description': '',
        'cover_url': cover_url,
    }

def add_book(query: str = "", title: str = "", author: str = "", isbn: str = "",
             status: str = "read", rating: int = None, photo_path: str = None,
             custom_cover: str = None, year: int = None, publisher: str = None,
             pages: int = None, genres: list = None, description: str = None,
             force: bool = False):
    search_q = (query or "").strip() or f"{author} {title}".strip()
    book_info = None

    # If title and author are not fully given or search requested, try online APIs
    should_search = bool(query or isbn or not (title and author and custom_cover and year))
    if should_search:
        if not search_q and not isbn:
            print("[!] Укажите название, автора или ISBN для поиска.")
            return False

        print(f"[*] Поиск информации для: «{search_q or isbn}»...")
        book_info = search_google_books(search_q, isbn=isbn)
        if not book_info:
            print("[*] Поиск в Google Books не дал результатов, пробуем Open Library...")
            book_info = search_open_library(search_q, isbn=isbn)

    if not book_info:
        book_info = {
            'title': title or search_q or 'Без названия',
            'author': author or 'Неизвестный автор',
            'year': year,
            'publisher': publisher or '',
            'isbn': isbn or '',
            'pages': pages,
            'genres': genres or [],
            'language': 'ru',
            'description': description or '',
            'cover_url': custom_cover
        }
    else:
        # Override with explicit values if provided
        if title:
            book_info['title'] = title
        if author:
            book_info['author'] = author
        if isbn:
            book_info['isbn'] = isbn
        if year:
            book_info['year'] = year
        if publisher:
            book_info['publisher'] = publisher
        if pages:
            book_info['pages'] = pages
        if genres:
            book_info['genres'] = genres
        if description:
            book_info['description'] = description
        if custom_cover:
            book_info['cover_url'] = custom_cover

    final_title = (book_info.get('title') or title or search_q or 'Без названия').strip()
    if not final_title:
        final_title = 'Без названия'
    final_author = (book_info.get('author') or author or 'Неизвестный автор').strip()
    if not final_author:
        final_author = 'Неизвестный автор'
    book_info['title'] = final_title
    book_info['author'] = final_author
    slug = f"{slugify(final_author)}-{slugify(final_title)}"

    md_file = BOOKS_DIR / f"{slug}.md"
    if md_file.exists() and not force:
        print(f"[!] Файл книги уже существует: {md_file.name}. Используйте --force для перезаписи.", file=sys.stderr)
        return False

    # Determine cover
    cover_rel_path = "/covers/default-book.svg"
    cover_target = COVERS_DIR / f"{slug}.jpg"

    cover_to_download = book_info.get('cover_url')
    if cover_to_download:
        if cover_to_download.startswith('/covers/') or cover_to_download.startswith('covers/'):
            cover_rel_path = cover_to_download if cover_to_download.startswith('/') else f"/{cover_to_download}"
        else:
            print(f"[*] Скачивание обложки: {cover_to_download}...")
            if download_image(cover_to_download, cover_target):
                cover_rel_path = f"/covers/{slug}.jpg"
                print(f"[✓] Обложка сохранена в {cover_rel_path}")

    # Generate Markdown file
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    md_file = BOOKS_DIR / f"{slug}.md"
    year_str = f"year: {book_info['year']}\n" if book_info.get('year') else ""
    pub_str = f'publisher: {json.dumps(book_info["publisher"], ensure_ascii=False)}\n' if book_info.get('publisher') else ""
    isbn_str = f'isbn: {json.dumps(book_info["isbn"], ensure_ascii=False)}\n' if book_info.get('isbn') else ""
    pages_str = f"pages: {book_info['pages']}\n" if book_info.get('pages') else ""
    rating_str = f"rating: {rating}\n" if rating else ""
    genres_list = book_info.get('genres', [])
    genres_yaml = "genres:\n" + "".join([f'  - {json.dumps(g, ensure_ascii=False)}\n' for g in genres_list]) if genres_list else "genres: []\n"

    desc = (book_info.get('description') or '').strip()
    if desc:
        desc = clean_description(desc)
    if not desc:
        desc = f"Экземпляр бумажной книги «{final_title}» ({final_author})."

    content = f"""---
title: {json.dumps(final_title, ensure_ascii=False)}
author: {json.dumps(final_author, ensure_ascii=False)}
{year_str}{pub_str}{isbn_str}language: {json.dumps(book_info.get('language') or 'ru', ensure_ascii=False)}
{pages_str}cover: {json.dumps(cover_rel_path, ensure_ascii=False)}
{genres_yaml}status: {json.dumps(status, ensure_ascii=False)}
{rating_str}addedAt: {date.today().isoformat()}
---

{desc}
"""

    tmp_md = md_file.with_name(f"{md_file.name}.tmp")
    with open(tmp_md, 'w', encoding='utf-8') as f:
        f.write(content)
    tmp_md.replace(md_file)
    try:
        rel_md = md_file.relative_to(ROOT_DIR)
    except ValueError:
        rel_md = md_file
    print(f"[✓] Запись книги создана: {rel_md}")

    # Move processed photo if given
    if photo_path:
        p = Path(photo_path)
        if not p.is_absolute() and not p.exists():
            if (ROOT_DIR / photo_path).exists():
                p = ROOT_DIR / photo_path
            elif (INCOMING_DIR / photo_path).exists():
                p = INCOMING_DIR / photo_path
            elif (INCOMING_DIR / p.name).exists():
                p = INCOMING_DIR / p.name

        if p.exists() and p.is_file():
            PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
            if p.resolve().parent == PROCESSED_DIR.resolve():
                print(f"[*] Исходное фото уже находится в {PROCESSED_DIR.name}/, перемещение пропущено")
            else:
                dest = PROCESSED_DIR / p.name
                if dest.exists():
                    stem = p.stem
                    suffix = p.suffix
                    counter = 1
                    while (PROCESSED_DIR / f"{stem}_{counter}{suffix}").exists():
                        counter += 1
                    dest = PROCESSED_DIR / f"{stem}_{counter}{suffix}"
                shutil.move(str(p), str(dest))
                try:
                    rel_dest = dest.relative_to(ROOT_DIR)
                except ValueError:
                    rel_dest = dest
                print(f"[✓] Исходное фото перемещено в {rel_dest}")
        elif p.exists():
            print(f"[!] Внимание: указанный путь не является файлом фотографии: {photo_path}", file=sys.stderr)
        else:
            print(f"[!] Внимание: файл фотографии не найден: {photo_path}", file=sys.stderr)

    return True

def main():
    parser = argparse.ArgumentParser(description="Добавить книгу в каталог books.vitalik.dev")
    parser.add_argument("-q", "--query", help="Поисковый запрос (например '1984 Оруэлл')")
    parser.add_argument("-t", "--title", help="Название книги")
    parser.add_argument("-a", "--author", help="Автор")
    parser.add_argument("-i", "--isbn", help="ISBN книги")
    parser.add_argument("-y", "--year", type=int, help="Год издания")
    parser.add_argument("-pub", "--publisher", help="Издательство")
    parser.add_argument("--pages", type=int, help="Количество страниц")
    parser.add_argument("-g", "--genres", nargs="*", help="Список жанров через пробел")
    parser.add_argument("-d", "--desc", help="Описание или аннотация книги")
    parser.add_argument("-s", "--status", choices=["read", "reading", "to-read", "planned", "neutral"], default="read", help="Статус прочтения")
    parser.add_argument("-r", "--rating", type=int, choices=[1, 2, 3, 4, 5], help="Оценка от 1 до 5")
    parser.add_argument("-p", "--photo", help="Путь к файлу фотографии из incoming_photos/")
    parser.add_argument("-c", "--cover", help="Прямой URL качественной обложки")
    parser.add_argument("-f", "--force", action="store_true", help="Перезаписать существующую запись книги")

    args = parser.parse_args()

    if not (args.query or args.title or args.isbn):
        parser.print_help()
        sys.exit(1)

    success = add_book(
        query=args.query or "",
        title=args.title or "",
        author=args.author or "",
        isbn=args.isbn or "",
        status=args.status,
        rating=args.rating,
        photo_path=args.photo,
        custom_cover=args.cover,
        year=args.year,
        publisher=args.publisher,
        pages=args.pages,
        genres=args.genres or [],
        description=args.desc or "",
        force=args.force
    )
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
