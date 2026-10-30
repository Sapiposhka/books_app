from PyQt6.QtWidgets import QMainWindow, QMessageBox
from generate_ui.login_ui import Ui_MainWindow
from db.database import Database
from windows.main_app_window import MainApp
from windows.registration_window import Registration


class Login(QMainWindow, Ui_MainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.setupUi(self)
        self.db = db
        self._connect_ui()

    def _connect_ui(self) -> None:
        self.btn_login.clicked.connect(self._open_main_app)
        self.btn_registration.clicked.connect(self._open_registration)

    def _open_main_app(self):
        self.main_app = MainApp()
        self.main_app.show()
        self.close()

    def _open_registration(self):
        self.registration = Registration()
        self.registration.show()
        self.close()

