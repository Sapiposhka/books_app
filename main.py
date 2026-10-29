import sys
from PyQt6.QtWidgets import QApplication
import build_ui
from main_window import Login


def main() -> None:
    app = QApplication(sys.argv)
    window = Login()
    window.show()
    sys.exit(app.exec())

def custom_excepthook(exc_type, exc_value, exc_tb):
    error_message = f"Необработанное исключение: {exc_type.__name__}: {exc_value}"
    print(error_message)
    sys.excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = custom_excepthook


if __name__ == '__main__':
    main()