import shutil
import sys
from pathlib import Path

FROZEN = getattr(sys, 'frozen', False)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent

DB_PATH = APP_DIR / 'db' / 'books_app_db.sqlite'
FILES_DIR = APP_DIR / 'files'


def ensure_database() -> Path:
    """Возвращает путь к базе. В exe при первом запуске копирует в неё базу, вшитую в сборку."""
    if not DB_PATH.exists():
        bundled = Path(getattr(sys, '_MEIPASS', APP_DIR)) / 'db' / 'books_app_db.sqlite'
        if FROZEN and bundled.exists():
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled, DB_PATH)
        else:
            raise FileNotFoundError(f'Не найдена база данных: {DB_PATH}')
    return DB_PATH
