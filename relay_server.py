"""Servidor de reunión simple para Secure Chat.

Permite que los usuarios se conecten utilizando códigos de seis dígitos en lugar
de intercambiar direcciones IP. El servidor mantiene un registro temporal de los
pares código -> (IP, puerto). Los códigos se consumen al usarse una vez.

Ejecución:
    python relay_server.py

El servidor escucha en ``0.0.0.0:8000`` por defecto.
"""

from __future__ import annotations

import json
import random
import string
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Tuple


codes: Dict[str, Tuple[str, int]] = {}


class RelayHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # pragma: no cover - servidor auxiliar
        if self.path != "/register":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length))
        code = "".join(random.choices(string.digits, k=6))
        codes[code] = (data["ip"], int(data["port"]))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"code": code}).encode("utf-8"))

    def do_GET(self) -> None:  # pragma: no cover - servidor auxiliar
        if not self.path.startswith("/lookup/"):
            self.send_error(404)
            return
        code = self.path.rsplit("/", 1)[-1]
        if code not in codes:
            self.send_error(404)
            return
        ip, port = codes.pop(code)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ip": ip, "port": port}).encode("utf-8"))

    def log_message(self, _format: str, *_args: str) -> None:  # pragma: no cover
        return


def main() -> None:  # pragma: no cover - punto de entrada manual
    server = HTTPServer(("0.0.0.0", 8000), RelayHandler)
    print("Relay server listening on port 8000")
    server.serve_forever()


if __name__ == "__main__":
    main()

