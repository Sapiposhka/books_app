import json
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QRadioButton, QWidget
from db.database import Database
from generate_ui.questionnaire_ui import Ui_QuestionnaireWidget


files_path = Path('files')


class Questionnaire(QWidget, Ui_QuestionnaireWidget):
    def __init__(self, db: Database, user_id: int):
        super().__init__()
        self.setupUi(self)
        self.db = db
        self.user_id = user_id

        self.groups = {
            'genre': self.group_genre,
            'audience': self.group_audience,
            'rating': self.group_rating,
            'volume': self.group_volume,
            'era': self.group_era,
        }

        self.btn_skip.clicked.connect(self._skip)
        self.btn_done.clicked.connect(self._done)

    def _get_answer(self, question: str) -> str | None:
        for button in self.groups[question].findChildren(QRadioButton):
            if button.isChecked():
                return button.objectName().removeprefix(f'{question}_')
        return None

    def _collect_answers(self) -> dict[str, str | None]:
        return {
            question: self._get_answer(question)
            for question in self.groups
        }

    def _skip(self) -> None:
        self._open_mood_questionnaire()

    def _done(self) -> None:
        answers = self._collect_answers()

        if any(answer is None for answer in answers.values()):
            QMessageBox.warning(
                self,
                'Внимание',
                'Ответьте, пожалуйста, на все вопросы или нажмите «Пропустить».',
            )
            return

        try:
            self._save_answers(answers)
        except (OSError, json.JSONDecodeError) as error:
            QMessageBox.critical(
                self,
                'Ошибка',
                f'Не удалось сохранить результаты опроса: {error}',
            )
            return

        self._open_mood_questionnaire()

    def _save_answers(self, answers: dict[str, str | None]) -> None:
        files_path.mkdir(parents=True, exist_ok=True)
        path = files_path.joinpath(
            f'questionnaire_user_{self.user_id}.json'
        )

        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
        else:
            data = {
                'user_id': self.user_id,
                'mood': None,
            }

        data['user_id'] = self.user_id
        data['answers'] = answers
        data['initial_shown'] = True

        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=4),
            encoding='utf-8',
        )

    def _open_mood_questionnaire(self) -> None:
        from windows.mood_questionnaire_window import MoodQuestionnaire

        self.mood_window = MoodQuestionnaire(self.db, self.user_id)
        self.mood_window.show()
        self.close()
