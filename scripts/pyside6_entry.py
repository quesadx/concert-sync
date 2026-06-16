"""Unified entry point for ConcertSync PySide6 GUI (packaged and development).
Double-click the .exe to launch the seat reservation client (default).
Pass --mode dashboard for the server monitoring dashboard.

In Windows the .exe includes everything — no Python or PySide6 needed.
"""
import os
import sys
import argparse

# ── Platform-appropriate Qt platform plugin ────────────────────────────
# xcb is Linux-only; Windows auto-detects its own platform plugin.
if sys.platform == "linux":
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtWidgets import QApplication  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="ConcertSync PySide6 GUI")
    parser.add_argument(
        "--mode",
        choices=["client", "dashboard"],
        default="client",
        help="Launch mode: client (seat reservation UI) or dashboard (server monitoring)",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)

    if args.mode == "dashboard":
        from frontend_pyside6.server_dashboard import ServerDashboardWindow  # noqa: E402
        window = ServerDashboardWindow()
    else:
        from frontend_pyside6.main_window import ConcertMainWindow  # noqa: E402
        window = ConcertMainWindow()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
