import json
from pathlib import Path

from PyQt6.QtWidgets import QMessageBox, QRadioButton, QWidget

from db.database import Database
from generate_ui.mood_questionnaire_ui import Ui_MoodQuestionnaireWidget


FILES_DIR = Path(__file__).resolve().parent.parent / 'files'


class MoodQuestionnaire(QWidget, Ui_MoodQuestionnaireWidget):
    def __init__(self, db: Database, user_id: int):
        super().__init__()
        self.setupUi(self)

        self.db = db
        self.user_id = user_id

        self.btn_done.clicked.connect(self._finish_with_selected_mood)
        self.btn_skip.clicked.connect(self._skip_mood)

    def _get_selected_mood(self) -> str | None:
        for button in self.findChildren(QRadioButton):
            if button.isChecked() and button.objectName().startswith('mood_'):
                return button.objectName().removeprefix('mood_')

        return None

    def _save_mood(self, mood: str | None) -> None:
        FILES_DIR.mkdir(parents=True, exist_ok=True)
        path = FILES_DIR / f'questionnaire_user_{self.user_id}.json'

        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))

            if data.get('user_id') != self.user_id:
                raise ValueError('ID пользователя в JSON-файле не совпадает')
        else:
            data = {
                'user_id': self.user_id,
                'answers': {},
            }

        # Обновляем настроение, не удаляя ответы первичной анкеты.
        data['mood'] = mood

        temp_path = path.with_suffix('.json.tmp')
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=4),
            encoding='utf-8',
        )
        temp_path.replace(path)

    def _finish_with_selected_mood(self) -> None:
        mood = self._get_selected_mood()

        if mood is None:
            QMessageBox.warning(
                self,
                'Внимание',
                'Выберите настроение или нажмите «Пропустить».',
            )
            return

        try:
            self._save_mood(mood)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                'Ошибка',
                f'Не удалось сохранить настроение: {error}',
            )
            return

        self._open_main_app()

    def _skip_mood(self) -> None:
        try:
            # при пропуске сегодняшнее настроение не учитываем.
            self._save_mood(None)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                'Ошибка',
                f'Не удалось сохранить результат опроса: {error}',
            )
            return

        self._open_main_app()

    def _open_main_app(self) -> None:
        from windows.main_app_window import MainApp

        self.main_app = MainApp(self.db, self.user_id)
        self.main_app.show()
        self.close()
