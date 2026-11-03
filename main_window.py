from PyQt6.QtWidgets import QMainWindow, QMessageBox, QLineEdit
from generate_ui.login_ui import Ui_MainWindow
from db.database import Database
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

        user_id = self.db.authenticate(email, password)
        if user_id is None:
            QMessageBox.warning(self, 'Ошибка', 'Неверный email или пароль')
            return
        
        self.questionnaire = Questionnaire(self.db, user_id)
        self.questionnaire.show()
        self.close()

    def _open_registration(self):
        self.registration = Registration(self.db)
        self.registration.show()
        self.close()

