from src.server.concert_server import ConcertServer
from frontend_tui.app import ConcertTextualApp


def main():
    server = ConcertServer(port=9999)
    print("Starting ConcertSync desktop launcher on port 9999")
    server.start()

    app = ConcertTextualApp()
    try:
        app.run()
    finally:
        server.stop()


if __name__ == "__main__":
    main()