import sys
from src.server.concert_server import ConcertServer


def _run_tui():
    """Original Textual TUI mode (preserved)."""
    from frontend_tui.app import ConcertTextualApp
    app = ConcertTextualApp()
    app.run()


def _run_pyside6():
    """New PySide6 GUI client mode."""
    from PySide6.QtWidgets import QApplication
    from frontend_pyside6.main_window import ConcertMainWindow
    app = QApplication(sys.argv)
    window = ConcertMainWindow()
    window.show()
    sys.exit(app.exec())


def _run_dashboard():
    """Server monitoring dashboard mode."""
    from PySide6.QtWidgets import QApplication
    from frontend_pyside6.server_dashboard import ServerDashboardWindow
    app = QApplication(sys.argv)
    window = ServerDashboardWindow()
    window.show()
    sys.exit(app.exec())


def _run_server_only():
    """Server-only mode (no UI)."""
    server = ConcertServer(port=9999)
    print("Server running on port 9999. Press Ctrl+C to stop.")
    server.start()
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        print("Server stopped.")


def main(mode: str = "both"):
    """Start ConcertSync in the specified mode.

    Args:
        mode: 'both' for server + client (default), 'server' for server only,
              'client' for PySide6 client only, 'dashboard' for server dashboard only,
              'tui' for Textual TUI with server.
    """
    if mode == "server":
        _run_server_only()
        return

    if mode == "client":
        _run_pyside6()
        return

    if mode == "dashboard":
        _run_dashboard()
        return

    if mode == "tui":
        server = ConcertServer(port=9999)
        print(f"Starting ConcertSync on port 9999 (TUI mode)")
        server.start()
        try:
            _run_tui()
        finally:
            server.stop()
        return

    # Default: both (server + PySide6 client)
    server = ConcertServer(port=9999)
    print(f"Starting ConcertSync on port 9999 (BOTH mode)")
    server.start()
    try:
        _run_pyside6()
    finally:
        server.stop()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ConcertSync Desktop Launcher")
    parser.add_argument(
        "--mode",
        choices=["both", "server", "client", "dashboard", "tui"],
        default="both",
        help="Launch mode: both (server+client), server, client, dashboard, or tui",
    )
    parser.add_argument(
        "--gui",
        choices=["tui", "pyside6"],
        default="pyside6",
        help="GUI frontend to use (legacy, use --mode instead)",
    )
    args = parser.parse_args()

    # Legacy --gui support: if --gui tui is passed, use tui mode
    if args.gui == "tui":
        main(mode="tui")
    else:
        main(mode=args.mode)
