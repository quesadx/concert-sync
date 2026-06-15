"""Entry point for the packaged ConcertSync PySide6 GUI.
Double-click the .exe, type the server IP, and click Connect.

In Windows the .exe includes everything — no Python or PySide6 needed.
"""
import os
import sys

if sys.platform == "linux":
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtWidgets import QApplication  # noqa: E402
from frontend_pyside6.main_window import ConcertMainWindow  # noqa: E402

app = QApplication(sys.argv)
window = ConcertMainWindow()
window.show()
sys.exit(app.exec())
