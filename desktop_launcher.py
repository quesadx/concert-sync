import sys
from src.server.concert_server import ConcertServer


def _run_tui():
    """Original Textual TUI mode (preserved)."""
    from frontend_tui.app import ConcertTextualApp
    app = ConcertTextualApp()
    app.run()


def _run_pyside6():
    """New PySide6 GUI mode."""
    from PySide6.QtWidgets import QApplication
    from frontend_pyside6.main_window import ConcertMainWindow
    app = QApplication(sys.argv)
    window = ConcertMainWindow()
    window.show()
    sys.exit(app.exec())


def main(gui: str = "pyside6"):
    """Start ConcertSync server + user interface.

    Args:
        gui: 'tui' for Textual terminal UI, 'pyside6' for PySide6 desktop GUI (default).
    """
    server = ConcertServer(port=9999)
    print(f"Starting ConcertSync on port 9999 ({gui.upper()} mode)")
    server.start()

    try:
        if gui == "tui":
            _run_tui()
        else:
            _run_pyside6()
    finally:
        server.stop()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ConcertSync Desktop Launcher")
    parser.add_argument("--gui", choices=["tui", "pyside6"], default="pyside6",
                        help="GUI frontend to use")
    args = parser.parse_args()
    main(gui=args.gui)
