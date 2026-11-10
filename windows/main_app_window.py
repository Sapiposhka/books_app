import json
import ssl
import threading
import urllib.request

import certifi
from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMainWindow, QPushButton

from db import Database
from generate_ui.main_app_ui import Ui_MainWindow
from recommender import recommend, validate_answers
from utils.paths import FILES_DIR
from windows.mood_questionnaire_window import MoodQuestionnaire


BATCH_SIZE = 100  # сколько книг подбираем за один раз
SWIPE_THRESHOLD = 120  # на сколько пикселей надо протянуть карточку, чтобы это засчиталось свайпом
MAX_DESC_LENGTH = 3000  # описания в датасете бывают очень длинными (длинное прокручивается)
LOAD_COVERS = True  # False - не загружать обложки из интернета


class MainApp(QMainWindow, Ui_MainWindow):
    cover_loaded = pyqtSignal(int, bytes)  # book_id, содержимое картинки

    def __init__(self, db: Database, user_id: int):
        super().__init__()
        self.setupUi(self)
        self._cover_pixmap = QPixmap()
        self.lbl_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.db = db
        self.user_id = user_id

        self.queue: list[dict] = []  # книги, которые ещё покажем
        self.current_book: dict | None = None
        self.seen: set[int] = set()  # лайкнутые и пропущенные в этой сессии
        self.preferences, self.mood = self._load_preferences()

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
        self.btn_mood.clicked.connect(self._open_mood_questionnaire)
        self.btn_logout.clicked.connect(self._logout)
        self.btn_preferences.clicked.connect(self._edit_preferences)
        # свайп мышью по карточке + стрелки на клавиатуре
        self.card_frame.installEventFilter(self)
        # перерисовываем обложку при каждом изменении размера области под неё
        self.lbl_cover.installEventFilter(self)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=self._like_by_key)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=self._skip_by_key)

    def _setup_favorites_page(self) -> None:
        self.fav_list = QListWidget()
        self.fav_list.setStyleSheet(
            'QListWidget { background-color: #ffffff; color: #2c3e50; }'
            'QListWidget::item { padding: 8px; }'
            'QListWidget::item:selected { background-color: #dbeafe; color: #1a202c; }'
        )
        self.btn_unlike = QPushButton('Убрать из избранного')
        self.btn_unlike.setStyleSheet('QPushButton { color: #000000; }')
        self.btn_unlike.clicked.connect(self._unlike_selected)
        self.fav_layout.addWidget(self.fav_list)
        self.fav_layout.addWidget(self.btn_unlike)
        self.fav_list.hide()
        self.btn_unlike.hide()

    def _load_preferences(self) -> tuple[dict, str | None]:
        path = FILES_DIR / f'questionnaire_user_{self.user_id}.json'

        try:
            with open(path, encoding='utf-8') as file:
                data = json.load(file)

            preferences = data.get('answers', {})
            mood = data.get('mood')

            if not isinstance(preferences, dict):
                preferences = {}

            validate_answers(preferences, mood)

            return preferences, mood

        except (OSError, ValueError, KeyError, TypeError):
            return {}, None

    # ---------- лента ----------

    def _fill_queue(self) -> None:
        candidates = self.db.books.get_books_for_recommendation(self.user_id)
        recommended = recommend(
            candidates,
            self.preferences,
            mood=self.mood,
            seen=self.seen,
            limit=BATCH_SIZE,
        )
        self.queue = self.db.books.get_books_by_ids([book['id'] for book in recommended])

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
        self._cover_pixmap = QPixmap()
        self.lbl_cover.setPixmap(QPixmap())
        self.lbl_cover.setText('📚 Обложка книги')

        url = str(book['cover_url'] or '')
        if not LOAD_COVERS or not url.startswith(('http://', 'https://')):
            return

        threading.Thread(
            target=self._download_cover,
            args=(book['id'], url),
            daemon=True,
        ).start()

    def _download_cover(self, book_id: int, url: str) -> None:
        try:
            request = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0'},
            )
            context = ssl.create_default_context(cafile=certifi.where())

            with urllib.request.urlopen(
                    request,
                    timeout=15,
                    context=context,
            ) as response:
                data = response.read(2_000_000)

            self.cover_loaded.emit(book_id, data)

        except Exception as error:
            print(f'Не удалось загрузить обложку {url}: {error}')

    def _on_cover_loaded(self, book_id: int, data: bytes) -> None:
        if self.current_book is None or self.current_book['id'] != book_id:
            return

        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            print(f'Картинка книги {book_id} не распозналась как изображение')
            return

        self._cover_pixmap = pixmap
        self._display_cover()

    def _display_cover(self) -> None:
        if self._cover_pixmap.isNull():
            return

        size = self.lbl_cover.contentsRect().size()
        if size.width() <= 0 or size.height() <= 0:
            return

        scaled = self._cover_pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.lbl_cover.setText('')
        self.lbl_cover.setPixmap(scaled)

    # ---------- действия ----------

    def _like(self) -> None:
        if self.current_book is None:
            return
        self.db.books.like_book(self.user_id, self.current_book['id'])
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
        if watched is self.lbl_cover and event.type() == QEvent.Type.Resize:
            self._display_cover()
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
        books = self.db.books.get_liked_books(self.user_id)
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
        self.db.books.unlike_book(self.user_id, book_id)
        self.seen.discard(book_id)
        self._refresh_favorites()

    def _open_mood_questionnaire(self) -> None:
        self.mood_window = MoodQuestionnaire(self.db, self.user_id)
        self.mood_window.show()
        self.close()

    def _logout(self) -> None:
        # импорт здесь, чтобы не создавать циклический импорт модулей.
        from windows.main_window import Login

        self.login_window = Login(self.db)
        self.login_window.show()
        self.close()

    def _edit_preferences(self) -> None:
        from windows.questionnaire_window import Questionnaire

        self.questionnaire_window = Questionnaire(self.db, self.user_id)
        self.questionnaire_window.show()
        self.close()
