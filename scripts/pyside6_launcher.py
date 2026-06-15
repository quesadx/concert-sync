"""Entry point for the packaged ConcertSync PySide6 GUI.
Double-click the .exe, type the server IP, and click Connect.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtWidgets import QApplication  # noqa: E402
from frontend_pyside6.main_window import ConcertMainWindow  # noqa: E402

app = QApplication(sys.argv)
window = ConcertMainWindow()
window.show()
sys.exit(app.exec())
