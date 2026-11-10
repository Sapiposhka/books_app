import sqlite3
from db.db_books import BooksDB
from db.db_users import UsersDB


class Database:
    def __init__(self) -> None:
        self.connection = sqlite3.connect('db/books_app_db.sqlite')
        self.connection.execute('PRAGMA foreign_keys = ON')
        self.users = UsersDB(self.connection)
        self.books = BooksDB(self.connection)

    def close(self) -> None:
        self.connection.close()
