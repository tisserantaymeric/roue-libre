"""Point d'entrée de Roue Libre."""

import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from rouelib.ui.theme import APP_QSS
from rouelib.ui.app import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Roue Libre")
    app.setStyleSheet(APP_QSS)
    font = QFont()
    font.setPointSize(11)
    app.setFont(font)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
