"""Entry point for the ConcertSync PySide6 desktop GUI.

Usage:
    python -m frontend_pyside6
"""

import sys

from PySide6.QtWidgets import QApplication

# WARNING: ConcertMainWindow is a forward reference — class not created until Plan 04.
# The try/except allows package structure validation before the widget is implemented.
try:
    from frontend_pyside6.main_window import ConcertMainWindow
except ImportError:
    ConcertMainWindow = None


def main():
    """Start the PySide6 application and run the Qt event loop."""
    if ConcertMainWindow is None:
        print(
            "ConcertMainWindow not yet implemented — complete Plan 04 first",
            file=sys.stderr,
        )
        sys.exit(1)

    app = QApplication(sys.argv)
    window = ConcertMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
