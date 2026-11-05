import hashlib
import hmac
import os
import sqlite3


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)


class Database:
    def __init__(self) -> None:
        self.connection = sqlite3.connect('db/books_app_db.sqlite')
        self.connection.execute('PRAGMA foreign_keys = ON')
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Создаёт таблицу лайков, если её ещё нет (Users и Books уже существуют)."""
        with self.connection:
            self.connection.execute(
                'CREATE TABLE IF NOT EXISTS Likes ('
                'user_id INTEGER NOT NULL REFERENCES Users(id) ON DELETE CASCADE, '
                'book_id INTEGER NOT NULL REFERENCES Books(id) ON DELETE CASCADE, '
                'date_of_creation TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, '
                'PRIMARY KEY (user_id, book_id))'
            )

    def register_user(self, email: str, password: str) -> bool:
        email = email.lower()
        salt = os.urandom(16)
        password_hash = _hash_password(password, salt)
        try:
            with self.connection:
                self.connection.execute(
                    'INSERT INTO Users (email, password, salt) VALUES (?, ?, ?)',
                    (email, password_hash, salt),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def authenticate(self, email: str, password: str) -> int | None:
        email = email.lower()
        row = self.connection.execute(
            'SELECT id, password, salt FROM Users WHERE email = ?',
            (email,),
        ).fetchone()
        if row is None:
            return None
        user_id, saved_hash, salt = row
        if hmac.compare_digest(saved_hash, _hash_password(password, salt)):
            return user_id
        return None


    _BOOK_COLUMNS = 'id, title, author, description, genres, rating, pages, pub_year, cover_url'

    def _rows_to_books(self, cursor: sqlite3.Cursor) -> list[dict]:
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    def get_book(self, book_id: int) -> dict | None:
        cursor = self.connection.execute(
            f'SELECT {self._BOOK_COLUMNS} FROM Books WHERE id = ?',
            (book_id,),
        )
        books = self._rows_to_books(cursor)
        return books[0] if books else None

    def get_books(self, limit: int = 50, offset: int = 0) -> list[dict]:
        cursor = self.connection.execute(
            f'SELECT {self._BOOK_COLUMNS} FROM Books ORDER BY id LIMIT ? OFFSET ?',
            (limit, offset),
        )
        return self._rows_to_books(cursor)

    def search_books(self, query: str, limit: int = 50) -> list[dict]:
        pattern = f'%{query.strip()}%'
        cursor = self.connection.execute(
            f'SELECT {self._BOOK_COLUMNS} FROM Books '
            'WHERE title LIKE ? OR author LIKE ? ORDER BY title LIMIT ?',
            (pattern, pattern, limit),
        )
        return self._rows_to_books(cursor)

    def get_unliked_books(self, user_id: int) -> list[dict]:
        cursor = self.connection.execute(
            f'SELECT {self._BOOK_COLUMNS} FROM Books '
            'WHERE id NOT IN (SELECT book_id FROM Likes WHERE user_id = ?)',
            (user_id,),
        )
        return self._rows_to_books(cursor)

    def get_books_for_recommendation(self, user_id: int) -> list[dict]:
        """Нелайкнутые книги без тяжёлых полей (описание, обложка) - для recommend()."""
        cursor = self.connection.execute(
            'SELECT id, genres, rating, pages, pub_year FROM Books '
            'WHERE id NOT IN (SELECT book_id FROM Likes WHERE user_id = ?)',
            (user_id,),
        )
        return self._rows_to_books(cursor)

    def get_books_by_ids(self, book_ids: list[int]) -> list[dict]:
        """Полные данные книг в том же порядке, в каком переданы id."""
        if not book_ids:
            return []
        placeholders = ', '.join('?' * len(book_ids))
        cursor = self.connection.execute(
            f'SELECT {self._BOOK_COLUMNS} FROM Books WHERE id IN ({placeholders})',
            [int(book_id) for book_id in book_ids],
        )
        by_id = {book['id']: book for book in self._rows_to_books(cursor)}
        return [by_id[int(book_id)] for book_id in book_ids if int(book_id) in by_id]

    def get_liked_books(self, user_id: int) -> list[dict]:
        cursor = self.connection.execute(
            'SELECT b.id, b.title, b.author, b.description, b.genres, b.rating, '
            'b.pages, b.pub_year, b.cover_url '
            'FROM Books b JOIN Likes l ON l.book_id = b.id '
            'WHERE l.user_id = ? ORDER BY l.date_of_creation DESC',
            (user_id,),
        )
        return self._rows_to_books(cursor)

    def like_book(self, user_id: int, book_id: int) -> bool:
        try:
            with self.connection:
                self.connection.execute(
                    'INSERT INTO Likes (user_id, book_id) VALUES (?, ?)',
                    (user_id, book_id),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def unlike_book(self, user_id: int, book_id: int) -> None:
        with self.connection:
            self.connection.execute(
                'DELETE FROM Likes WHERE user_id = ? AND book_id = ?',
                (user_id, book_id),
            )

    def is_liked(self, user_id: int, book_id: int) -> bool:
        row = self.connection.execute(
            'SELECT 1 FROM Likes WHERE user_id = ? AND book_id = ?',
            (user_id, book_id),
        ).fetchone()
        return row is not None

    def close(self) -> None:
        self.connection.close()