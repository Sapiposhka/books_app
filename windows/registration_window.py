from PyQt6.QtWidgets import QMainWindow
from generate_ui.registration_ui import Ui_MainWindow


class Registration(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)


