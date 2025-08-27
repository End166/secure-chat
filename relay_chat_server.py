"""Servidor de retransmisión para Secure Chat.

Permite que dos clientes se conecten usando un código de seis dígitos
sin necesidad de conocer sus direcciones IP. El servidor empareja a los
clientes que proporcionan el mismo código y reenvía los datos en ambos
sentidos.

Ejemplo de ejecución:
    python relay_chat_server.py
"""
from __future__ import annotations

import socket
import threading
from typing import Dict, List

rooms: Dict[str, List[socket.socket]] = {}
lock = threading.Lock()


def relay(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass


def handle_client(conn: socket.socket) -> None:
    try:
        code = b""
        while b"\n" not in code:
            chunk = conn.recv(1)
            if not chunk:
                conn.close()
                return
            code += chunk
        room = code.strip().decode("utf-8")
        with lock:
            if room in rooms:
                other = rooms.pop(room)[0]
                try:
                    other.sendall(b"READY\n")
                    conn.sendall(b"READY\n")
                except Exception:
                    other.close()
                    conn.close()
                    return
                threading.Thread(target=relay, args=(conn, other), daemon=True).start()
                threading.Thread(target=relay, args=(other, conn), daemon=True).start()
            else:
                rooms[room] = [conn]
    except Exception:
        conn.close()


def main() -> None:  # pragma: no cover - punto de entrada manual
    host = "0.0.0.0"
    port = 7000
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen()
    print(f"Relay chat server listening on port {port}")
    try:
        while True:
            conn, _ = sock.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
    finally:
        sock.close()


if __name__ == "__main__":
    main()
