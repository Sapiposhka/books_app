from os import system
from pathlib import Path


def build_ui() -> None:
    ui_path = Path('ui')
    ui_generate_path = Path('generate_ui')
    ui_files = list(ui_path.glob('*.ui'))
    
    for ui_file in ui_files:
        system(f'pyuic6 {ui_file} -o {ui_generate_path}/{ui_file.stem}_ui.py')

build_ui()