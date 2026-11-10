import json
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QLineEdit
from db import Database
from utils.paths import FILES_DIR
from generate_ui.login_ui import Ui_MainWindow
from windows.mood_questionnaire_window import MoodQuestionnaire
from windows.questionnaire_window import Questionnaire
from windows.registration_window import Registration


class Login(QMainWindow, Ui_MainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.setupUi(self)
        self.db = db
        self._connect_ui()

    def _connect_ui(self) -> None:
        self.line_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.btn_login.clicked.connect(self._login)
        self.btn_registration.clicked.connect(self._open_registration)

    def _login(self) -> None:
        email = self.line_login.text()
        password = self.line_password.text()

        if not email or not password:
            QMessageBox.warning(self, 'Ошибка', 'Заполните email и пароль')
            return

        user_id = self.db.users.authenticate(email, password)

        if user_id is None:
            QMessageBox.warning(self, 'Ошибка', 'Неверный email или пароль')
            return

        path = FILES_DIR / f'questionnaire_user_{user_id}.json'

        try:
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
            else:
                data = {}

            initial_shown = data.get(
                'initial_shown',
                bool(data.get('answers')),
            )

            data.update({
                'user_id': user_id,
                'initial_shown': True,
            })

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=4),
                encoding='utf-8',
            )
        except (OSError, json.JSONDecodeError) as error:
            QMessageBox.critical(
                self,
                'Ошибка',
                f'Не удалось сохранить данные анкеты: {error}',
            )
            return

        if initial_shown:
            self.next_window = MoodQuestionnaire(self.db, user_id)
        else:
            self.next_window = Questionnaire(self.db, user_id)

        self.next_window.show()
        self.close()

    def _open_registration(self):
        self.registration = Registration(self.db)
        self.registration.show()
        self.close()
