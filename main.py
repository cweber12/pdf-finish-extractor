import sys

from PyQt6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui import theme


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Finish Extractor")
    app.setStyleSheet(theme.STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
