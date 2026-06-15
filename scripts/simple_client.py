"""Minimal TCP client for ConcertSync demo — no dependencies beyond Python stdlib.
Connects to a server, queries seat map, reserves a seat, and confirms purchase.
"""

import socket
import json
import sys

SERVER_HOST = "192.168.1.42"
SERVER_PORT = 9999


def send(host: str, action: str, section: str = "GENERAL") -> dict:
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect((host, SERVER_PORT))
        s.sendall(json.dumps({"action": action, "section": section}).encode())
        chunks = []
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
        return json.loads(b"".join(chunks))
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
    finally:
        s.close()


def main():
    if len(sys.argv) > 1:
        host = sys.argv[1]
    else:
        host = SERVER_HOST

    print(f"Conectando a {host}:{SERVER_PORT}...")
    # 1. Ver disponibilidad
    r = send(host, "QUERY_SEAT_MAP", "VIP")
    if r.get("status") != "SUCCESS":
        print(f"Error conectando: {r.get('message', r)}")
        return

    seats = r["seat_map"]
    total = sum(len(row) for row in seats)
    libres = sum(1 for row in seats for s in row if s == "AVAILABLE")
    print(f"VIP: {libres}/{total} libres")

    # 2. Reservar un asiento
    r = send(host, "RESERVE", "VIP")
    if r["status"] != "SUCCESS":
        print(f"Error reservando: {r.get('message', r)}")
        return

    tx = r["transaction_id"]
    print(f"Reservado! TX: {tx}")

    # 3. Confirmar compra
    r = send(host, "CONFIRM", "VIP")
    if r["status"] == "SUCCESS":
        print("Compra confirmada!")
    else:
        print(f"Error confirmando: {r.get('message', r)}")


if __name__ == "__main__":
    main()
