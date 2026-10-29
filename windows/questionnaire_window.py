from PyQt6.QtWidgets import QMainWindow
from generate_ui.questionnaire_ui import Ui_MainWindow


class Questionnaire(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

