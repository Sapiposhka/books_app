import json
import threading
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMainWindow, QPushButton

from db.database import Database
from generate_ui.main_app_ui import Ui_MainWindow
from recommender import recommend

FILES_DIR = Path(__file__).resolve().parent.parent / 'files'

BATCH_SIZE = 100          # сколько книг подбираем за один раз
SWIPE_THRESHOLD = 120     # на сколько пикселей надо протянуть карточку, чтобы это засчиталось свайпом
MAX_DESC_LENGTH = 700     # описания в датасете бывают очень длинными
LOAD_COVERS = True        # False - не загружать обложки из интернета


class MainApp(QMainWindow, Ui_MainWindow):
    cover_loaded = pyqtSignal(int, bytes)  # book_id, содержимое картинки

    def __init__(self, db: Database, user_id: int):
        super().__init__()
        self.setupUi(self)
        self.db = db
        self.user_id = user_id

        self.queue: list[dict] = []     # книги, которые ещё покажем
        self.current_book: dict | None = None
        self.seen: set[int] = set()     # лайкнутые и пропущенные в этой сессии
        self.preferences = self._load_preferences()

        self._drag_start_x: float | None = None
        self._card_style = self.card_frame.styleSheet()

        self._setup_favorites_page()
        self._connect_ui()
        self._show_next_book()

    # ---------- настройка ----------

    def _connect_ui(self) -> None:
        self.cover_loaded.connect(self._on_cover_loaded)
        self.btn_like.clicked.connect(self._like)
        self.btn_skip.clicked.connect(self._skip)
        self.btn_feed.clicked.connect(self._open_feed)
        self.btn_favs.clicked.connect(self._open_favorites)
        # свайп мышью по карточке + стрелки на клавиатуре
        self.card_frame.installEventFilter(self)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=self._like_by_key)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=self._skip_by_key)

    def _setup_favorites_page(self) -> None:
        self.fav_list = QListWidget()
        self.btn_unlike = QPushButton('Убрать из избранного')
        self.btn_unlike.clicked.connect(self._unlike_selected)
        self.fav_layout.addWidget(self.fav_list)
        self.fav_layout.addWidget(self.btn_unlike)
        self.fav_list.hide()
        self.btn_unlike.hide()

    def _load_preferences(self) -> dict:
        """Ответы из files/questionnaire_user_<id>.json; если опрос пропущен - пустой словарь."""
        path = FILES_DIR / f'questionnaire_user_{self.user_id}.json'
        try:
            with open(path, encoding='utf-8') as file:
                answers = json.load(file)['answers']
            recommend([], answers)  # проверка, что ответы допустимые
            return answers
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    # ---------- лента ----------

    def _fill_queue(self) -> None:
        candidates = self.db.get_books_for_recommendation(self.user_id)
        recommended = recommend(
            candidates,
            self.preferences,
            seen=self.seen,
            limit=BATCH_SIZE,
        )
        self.queue = self.db.get_books_by_ids([book['id'] for book in recommended])

    def _show_next_book(self) -> None:
        if not self.queue:
            self._fill_queue()

        if not self.queue:
            self.current_book = None
            self.lbl_cover.setPixmap(QPixmap())
            self.lbl_cover.setText('📚')
            self.lbl_title.setText('Книги закончились')
            self.lbl_author.setText('')
            self.lbl_rating.setText('')
            self.lbl_desc.setText('Вы просмотрели все доступные книги.')
            self.btn_like.setEnabled(False)
            self.btn_skip.setEnabled(False)
            return

        self.btn_like.setEnabled(True)
        self.btn_skip.setEnabled(True)
        self.current_book = self.queue.pop(0)
        self._show_book(self.current_book)

    def _show_book(self, book: dict) -> None:
        self.lbl_title.setText(book['title'])
        self.lbl_author.setText(book['author'])

        details = []
        details.append(f"⭐ {book['rating']:.1f}" if book['rating'] is not None else '⭐ нет оценок')
        if book['pages']:
            details.append(f"{book['pages']} стр.")
        if book['pub_year']:
            details.append(str(book['pub_year']))
        self.lbl_rating.setText(' · '.join(details))

        description = str(book['description'] or 'Описания нет.')
        if len(description) > MAX_DESC_LENGTH:
            description = description[:MAX_DESC_LENGTH].rsplit(' ', 1)[0] + '…'
        self.lbl_desc.setText(description)

        self._load_cover(book)

    def _load_cover(self, book: dict) -> None:
        self.lbl_cover.setPixmap(QPixmap())
        self.lbl_cover.setText('📚 Обложка книги')
        url = str(book['cover_url'] or '')
        if not LOAD_COVERS or not url.startswith(('http://', 'https://')):
            return
        # скачиваем в отдельном потоке обычным urllib, чтобы не блокировать окно
        threading.Thread(
            target=self._download_cover, args=(book['id'], url), daemon=True
        ).start()

    def _download_cover(self, book_id: int, url: str) -> None:
        """Работает в фоновом потоке: нельзя трогать виджеты, только отправить сигнал."""
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'books_app/1.0'})
            with urllib.request.urlopen(request, timeout=8) as response:
                data = response.read(2_000_000)
        except Exception:
            return  # нет обложки или нет сети - остаётся заглушка
        try:
            self.cover_loaded.emit(book_id, data)
        except RuntimeError:
            pass  # окно уже закрыто

    def _on_cover_loaded(self, book_id: int, data: bytes) -> None:
        # пользователь мог уже перелистнуть на другую книгу
        if self.current_book is None or self.current_book['id'] != book_id:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.lbl_cover.setPixmap(
                pixmap.scaledToHeight(self.lbl_cover.maximumHeight(), Qt.TransformationMode.SmoothTransformation)
            )

    # ---------- действия ----------

    def _like(self) -> None:
        if self.current_book is None:
            return
        self.db.like_book(self.user_id, self.current_book['id'])
        self.seen.add(self.current_book['id'])
        self._show_next_book()

    def _skip(self) -> None:
        if self.current_book is None:
            return
        self.seen.add(self.current_book['id'])
        self._show_next_book()

    def _like_by_key(self) -> None:
        if self.stackedWidget.currentWidget() is self.page_feed:
            self._like()

    def _skip_by_key(self) -> None:
        if self.stackedWidget.currentWidget() is self.page_feed:
            self._skip()

    # ---------- свайп ----------

    def eventFilter(self, watched, event) -> bool:
        if watched is self.card_frame:
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_start_x = event.globalPosition().x()
            elif event_type == QEvent.Type.MouseMove and self._drag_start_x is not None:
                self._show_swipe_hint(event.globalPosition().x() - self._drag_start_x)
            elif event_type == QEvent.Type.MouseButtonRelease and self._drag_start_x is not None:
                delta = event.globalPosition().x() - self._drag_start_x
                self._drag_start_x = None
                self.card_frame.setStyleSheet(self._card_style)
                if delta > SWIPE_THRESHOLD:
                    self._like()
                elif delta < -SWIPE_THRESHOLD:
                    self._skip()
        return super().eventFilter(watched, event)

    def _show_swipe_hint(self, delta: float) -> None:
        """Зелёная рамка при свайпе вправо (лайк), красная - влево (пропуск)."""
        if delta > SWIPE_THRESHOLD:
            color = '#38a169'
        elif delta < -SWIPE_THRESHOLD:
            color = '#e53e3e'
        else:
            self.card_frame.setStyleSheet(self._card_style)
            return
        self.card_frame.setStyleSheet(
            self._card_style + f'QFrame#card_frame {{ border: 3px solid {color}; }}'
        )

    # ---------- избранное ----------

    def _open_feed(self) -> None:
        self.stackedWidget.setCurrentWidget(self.page_feed)

    def _open_favorites(self) -> None:
        self._refresh_favorites()
        self.stackedWidget.setCurrentWidget(self.page_favorites)

    def _refresh_favorites(self) -> None:
        self.fav_list.clear()
        books = self.db.get_liked_books(self.user_id)
        for book in books:
            item = QListWidgetItem(f"{book['title']} — {book['author']}")
            item.setData(Qt.ItemDataRole.UserRole, book['id'])
            item.setToolTip(str(book['description'] or '')[:MAX_DESC_LENGTH])
            self.fav_list.addItem(item)

        has_books = bool(books)
        self.lbl_fav_placeholder.setVisible(not has_books)
        self.fav_list.setVisible(has_books)
        self.btn_unlike.setVisible(has_books)

    def _unlike_selected(self) -> None:
        item = self.fav_list.currentItem()
        if item is None:
            return
        book_id = item.data(Qt.ItemDataRole.UserRole)
        self.db.unlike_book(self.user_id, book_id)
        self.seen.discard(book_id)
        self._refresh_favorites()
