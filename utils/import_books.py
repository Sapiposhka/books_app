"""Импорт книг из CSV в db/books_app_db.sqlite.

Запуск (из папки проекта):
    python import_books.py путь/к/books.csv
    python import_books.py "C:/Users/Jurich/Downloads/books_dataset.csv" --limit 5000     # только первые 5000 строк
    python import_books.py путь/к/books.csv --clear          # сначала очистить таблицу Books

Названия колонок в CSV определяются автоматически по списку возможных вариантов (COLUMN_ALIASES).
Если какая-то колонка не нашлась, скрипт покажет, какие колонки есть в файле, - добавьте нужное
название в COLUMN_ALIASES.
"""
import argparse
import ast
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'db' / 'books_app_db.sqlite'

# поле в БД -> возможные названия колонки в CSV (в нижнем регистре)
COLUMN_ALIASES = {
    'title': ['title', 'book_title', 'book_name', 'name'],
    'author': ['author', 'authors', 'author_name', 'book_author'],
    'description': ['description', 'desc', 'summary', 'synopsis', 'book_description'],
    'genres': ['genres', 'genre', 'categories', 'category', 'shelves', 'subjects'],
    'rating': ['rating', 'average_rating', 'avg_rating', 'rating_avg', 'book_rating'],
    'pages': ['pages', 'num_pages', 'page_count', 'number_of_pages', 'pagecount'],
    'pub_year': ['pub_year', 'publication_year', 'publish_year', 'published_year', 'year',
                 'original_publication_year', 'publication_date', 'published_date',
                 'publish_date', 'first_publish_date', 'date_published'],
    'isbn': ['isbn13', 'isbn', 'isbn_13'],
    'cover_url': ['cover_url', 'image_url', 'cover_image', 'cover', 'image', 'img_url',
                  'thumbnail', 'thumbnail_url', 'small_thumbnail'],
}
REQUIRED = ['title']

BOOKS_SCHEMA = '''
CREATE TABLE Books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    author      TEXT NOT NULL,
    description TEXT,
    genres      TEXT NOT NULL DEFAULT '[]',
    rating      REAL CHECK (rating IS NULL OR rating BETWEEN 0 AND 5),
    pages       INTEGER,
    pub_year    INTEGER,
    cover_url   TEXT
)
'''


def find_columns(header: list[str]) -> dict[str, str]:
    lowered = {name.strip().lower(): name for name in header}
    found = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                found[field] = lowered[alias]
                break
    return found


def clean_text(value) -> str:
    return (value or '').strip()


def parse_genres(value) -> list[str]:
    """'Fantasy, Fiction' / "['Fantasy', 'Fiction']" / '["Fantasy"]' / 'a|b' -> ['fantasy', 'fiction']."""
    text = clean_text(value)
    if not text:
        return []
    items = None
    if text[0] in '[(':
        for parser in (json.loads, ast.literal_eval):
            try:
                items = parser(text)
                break
            except (ValueError, SyntaxError):
                continue
    if not isinstance(items, (list, tuple)):
        items = re.split(r'[,;|/]', text)

    genres = []
    for item in items:
        # в датасете встречаются составные жанры вроде "mystery, thriller, crime" - разбиваем их
        for genre in str(item).split(','):
            genre = genre.strip().lower()
            if genre and genre not in genres:
                genres.append(genre)
    return genres


def parse_rating(value) -> float | None:
    try:
        rating = float(clean_text(value))
    except ValueError:
        return None
    return rating if 0 <= rating <= 5 else None


def parse_pages(value) -> int | None:
    match = re.search(r'\d+', clean_text(value))
    if not match:
        return None
    pages = int(match.group())
    return pages if pages > 0 else None


def parse_year(value) -> int | None:
    match = re.search(r'(?<!\d)(\d{4})(?!\d)', clean_text(value))
    if not match:
        return None
    year = int(match.group(1))
    return year if 1000 <= year <= 2100 else None


def parse_author(value) -> str:
    text = clean_text(value)
    if text and text[0] == '[':
        try:
            items = ast.literal_eval(text)
            text = ', '.join(str(item).strip() for item in items)
        except (ValueError, SyntaxError):
            pass
    return text or 'Неизвестный автор'


def make_cover_url(isbn_value) -> str | None:
    """В датасете нет обложек, поэтому берём их из Open Library по ISBN.

    default=false: если обложки нет, сервер отвечает 404, и приложение оставляет заглушку.
    """
    isbn = re.sub(r'\D', '', clean_text(isbn_value))
    if len(isbn) not in (10, 13):
        return None
    return f'https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false'


def row_to_book(row: dict, columns: dict[str, str]) -> tuple | None:
    def get(field):
        column = columns.get(field)
        return row.get(column) if column else None

    title = clean_text(get('title'))
    if not title:
        return None
    return (
        title,
        parse_author(get('author')),
        clean_text(get('description')) or None,
        json.dumps(parse_genres(get('genres')), ensure_ascii=False),
        parse_rating(get('rating')),
        parse_pages(get('pages')),
        parse_year(get('pub_year')),
        clean_text(get('cover_url')) or make_cover_url(get('isbn')),
    )


def prepare_books_table(connection: sqlite3.Connection, clear: bool) -> None:
    """Создаёт Books, а если она пустая и с неверными типами колонок - пересоздаёт."""
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'Books'"
    ).fetchone()
    if not exists:
        connection.execute(BOOKS_SCHEMA)
        return

    types = {row[1]: row[2].upper() for row in connection.execute('PRAGMA table_info(Books)')}
    count = connection.execute('SELECT COUNT(*) FROM Books').fetchone()[0]
    wrong_types = types.get('description') != 'TEXT' or types.get('cover_url') != 'TEXT'

    if wrong_types and count == 0:
        print('Таблица Books пустая и с неверными типами колонок - пересоздаю с правильными.')
        connection.execute('DROP TABLE Books')
        connection.execute(BOOKS_SCHEMA)
    elif clear:
        connection.execute('DELETE FROM Books')
    elif wrong_types:
        print('Внимание: в Books типы description/cover_url должны быть TEXT. '
              'Таблица не пустая, поэтому я её не меняю.')


def import_csv(csv_path: Path, limit: int | None, clear: bool) -> None:
    csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))  # описания бывают очень длинными

    with open(csv_path, encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        columns = find_columns(reader.fieldnames or [])
        print('Колонки в файле:', reader.fieldnames)
        print('Сопоставление полей:', columns)

        missing = [field for field in REQUIRED if field not in columns]
        if missing:
            sys.exit(f'Не найдены обязательные колонки: {missing}. Добавьте названия из файла в COLUMN_ALIASES.')

        connection = sqlite3.connect(DB_PATH)
        prepare_books_table(connection, clear)

        # не добавляем уже существующие книги
        known = {
            (title.lower(), author.lower()): (book_id, cover_url)
            for book_id, title, author, cover_url in connection.execute(
                'SELECT id, title, author, cover_url FROM Books'
            )
        }
        batch, added, skipped = [], 0, 0
        insert = (
            'INSERT INTO Books (title, author, description, genres, rating, pages, pub_year, cover_url) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
        )
        for number, row in enumerate(reader, start=1):
            if limit and number > limit:
                break
            book = row_to_book(row, columns)
            if book is None:
                skipped += 1
                continue

            key = (book[0].lower(), book[1].lower())

            if key in known:
                book_id, old_cover_url = known[key]
                new_cover_url = book[7]

                if book_id is not None and not old_cover_url and new_cover_url:
                    connection.execute(
                        'UPDATE Books SET cover_url = ? WHERE id = ?',
                        (new_cover_url, book_id),
                    )
                    known[key] = (book_id, new_cover_url)

                skipped += 1
                continue

            known[key] = (None, book[7])
            batch.append(book)
            if len(batch) >= 5000:
                connection.executemany(insert, batch)
                added += len(batch)
                batch.clear()
        if batch:
            connection.executemany(insert, batch)
            added += len(batch)
        connection.commit()
        connection.close()

    print(f'Готово: добавлено {added}, пропущено (пустые или дубликаты) {skipped}.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Импорт книг из CSV в базу приложения')
    parser.add_argument('csv_path', type=Path)
    parser.add_argument('--limit', type=int, help='импортировать только первые N строк')
    parser.add_argument('--clear', action='store_true', help='очистить таблицу Books перед импортом')
    args = parser.parse_args()
    import_csv(args.csv_path, args.limit, args.clear)
