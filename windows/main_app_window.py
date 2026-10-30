from PyQt6.QtWidgets import QMainWindow
from generate_ui.main_app_ui import Ui_MainWindow
from db.database import Database


class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self, db: Database, user_id: int):
        super().__init__()
        self.setupUi(self)
        self.db = db
        self.user_id = user_id


