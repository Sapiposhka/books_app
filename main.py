import sys
from PyQt6.QtWidgets import QApplication
import build_ui
from db.database import Database
from main_window import Login


def main() -> None:
    app = QApplication(sys.argv)
    db = Database()
    window = Login(db)
    window.show()
    app_exit = app.exec()
    db.close()
    sys.exit(app_exit)

def custom_excepthook(exc_type, exc_value, exc_tb):
    error_message = f"Необработанное исключение: {exc_type.__name__}: {exc_value}"
    print(error_message)
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = custom_excepthook


if __name__ == '__main__':
    main()
