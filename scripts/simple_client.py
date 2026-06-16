"""Minimal TCP client for ConcertSync demo — no dependencies beyond Python stdlib.
Connects to a server, queries seat map, reserves a seat, and confirms purchase.
"""

import socket
import json
import sys
import uuid

SERVER_PORT = 9999


def send(host: str, action: str, user_id: str, section: str = "VIP") -> dict:
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect((host, SERVER_PORT))
        payload = {"action": action, "user_id": user_id, "section": section}
        s.sendall(json.dumps(payload).encode())
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
    if len(sys.argv) > 2:
        host = sys.argv[1]
        user_id = sys.argv[2]
    elif len(sys.argv) > 1:
        host = sys.argv[1]
        user_id = f"demo-{uuid.uuid4().hex[:8]}"
    else:
        host = input("IP del servidor: ").strip()
        nombre = input("Tu nombre (o Enter para anónimo): ").strip()
        user_id = nombre if nombre else f"demo-{uuid.uuid4().hex[:8]}"

    print(f"\nConectando a {host}:{SERVER_PORT} como {user_id}...")

    r = send(host, "QUERY_SEAT_MAP", user_id, "VIP")
    if r.get("status") != "SUCCESS":
        print(f"Error conectando: {r.get('message', r)}")
        input("\nPresioná Enter para salir...")
        return

    seats = r["seat_map"]
    total = sum(len(row) for row in seats)
    libres = sum(1 for row in seats for s in row if s == "AVAILABLE")
    print(f"VIP: {libres}/{total} libres")

    r = send(host, "RESERVE", user_id, "VIP")
    if r["status"] != "SUCCESS":
        print(f"Error reservando: {r.get('message', r)}")
        input("\nPresioná Enter para salir...")
        return

    tx = r["transaction_id"]
    print(f"Reservado! TX: {tx}")

    r = send(host, "CONFIRM", user_id, "VIP")
    if r["status"] == "SUCCESS":
        print("Compra confirmada!")
    else:
        print(f"Error confirmando: {r.get('message', r)}")

    input("\nPresioná Enter para salir...")


if __name__ == "__main__":
    main()
