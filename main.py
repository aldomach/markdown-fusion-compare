"""
main.py
Entry point for Obsidian Markdown Comparator.
Usage:
    python main.py
    python main.py nota1.md nota2.md
"""

import sys
import os

from PySide6.QtWidgets import QApplication

from ui.styles import STYLESHEET
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Obsidian Markdown Comparator")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()

    # Optional: load files from CLI arguments
    args = sys.argv[1:]
    if len(args) >= 1 and os.path.isfile(args[0]):
        window.left_panel._load_file(args[0])
    if len(args) >= 2 and os.path.isfile(args[1]):
        window.right_panel._load_file(args[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
