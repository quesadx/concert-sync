import argparse
import time

from src.server.concert_server import ConcertServer

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ConcertSync Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9999, help="Port to listen on")
    args = parser.parse_args()

    server = ConcertServer(host=args.host, port=args.port)
    print(f"Starting ConcertSync Server on {args.host}:{args.port}")
    server.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down ConcertSync Server")
        server.stop()
