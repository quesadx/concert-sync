import time

from src.server.concert_server import ConcertServer

if __name__ == "__main__":
    server = ConcertServer(port=9999)
    print("Starting ConcertSync Server...")
    server.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()