from PyQt6.QtWidgets import QMainWindow
from generate_ui.main_app_ui import Ui_MainWindow


class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)