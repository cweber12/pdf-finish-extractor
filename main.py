import sys

from PyQt6.QtWidgets import QApplication

from src.ui.style import theme
from src.ui.shell.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Finish Extractor")
    app.setStyleSheet(theme.STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

