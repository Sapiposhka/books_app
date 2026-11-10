import hmac
import os
import sqlite3

from utils.utils import _hash_password


class UsersDB:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

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
