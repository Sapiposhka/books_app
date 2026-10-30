from PyQt6.QtWidgets import QMainWindow, QMessageBox, QLineEdit
from generate_ui.registration_ui import Ui_MainWindow
from db.database import Database



class Registration(QMainWindow, Ui_MainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.setupUi(self)
        self.db = db
        self._connect_ui()

    def _connect_ui(self) -> None:
        self.line_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.line_password_repeat.setEchoMode(QLineEdit.EchoMode.Password)
        self.btn_register.clicked.connect(self._register)
        self.btn_back.clicked.connect(self._back_to_login)

    def _register(self) -> None:
        email = self.line_email.text()
        password = self.line_password.text()

        if not self.line_email.text() or not self.line_password.text() or not self.line_password_repeat.text():
            QMessageBox.warning(self, 'Ошибка', 'Заполните все поля')
        elif self.line_password.text() != self.line_password_repeat.text():
            QMessageBox.warning(self, 'Ошибка', 'Пароли в полях должны совпадать')
        elif '@' not in self.line_email.text():
            QMessageBox.warning(self, 'Ошибка', 'Некорректная почта')
        else:
            if self.db.register_user(email, password):
                QMessageBox.information(self, 'Готово', 'Регистрация прошла успешно')
                self._back_to_login()
            else:
                QMessageBox.warning(self, 'Ошибка', 'Такой email уже зарегистрирован')

    def _back_to_login(self) -> None:
        from main_window import Login
        self.login = Login(self.db)
        self.login.show()
        self.close()