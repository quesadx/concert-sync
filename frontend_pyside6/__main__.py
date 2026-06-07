"""Entry point for the ConcertSync PySide6 desktop GUI.

Usage:
    python -m frontend_pyside6
    python -m frontend_pyside6 --mode client
    python -m frontend_pyside6 --mode dashboard
"""

import sys
import argparse

from PySide6.QtWidgets import QApplication


def main():
    """Start the PySide6 application in the specified mode and run the Qt event loop."""
    parser = argparse.ArgumentParser(description="ConcertSync PySide6 Client")
    parser.add_argument(
        "--mode",
        choices=["client", "dashboard"],
        default="client",
        help="Launch mode: client (seat reservation UI) or dashboard (server monitoring)",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)

    if args.mode == "dashboard":
        from frontend_pyside6.server_dashboard import ServerDashboardWindow
        window = ServerDashboardWindow()
    else:
        from frontend_pyside6.main_window import ConcertMainWindow
        window = ConcertMainWindow()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
