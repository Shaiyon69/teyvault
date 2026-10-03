"""Wish history from PC to phone over the local network. The PC serves its UIGF export to whoever
knows a one-time PIN; the phone pulls it and imports it like a file. Cookies never leave the PC."""
import hmac
import http.server
import json
import os
import secrets
import socket
import threading
import urllib.error
import urllib.request

PORT = 47320  # fixed, so the address the phone remembers stays valid; random if taken
MAX_BAD_PINS = 5  # then the share stops, so a 6-digit PIN can't be brute-forced


def local_ip() -> str:
    """LAN address of this machine. UDP connect sends no packet, it only picks the interface."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
        except OSError:
            raise SystemExit("Not connected to a network.") from None
        return s.getsockname()[0]


class _Server(http.server.HTTPServer):
    # On Windows SO_REUSEADDR lets a second Teyvault bind the same port, and the phone then reaches
    # whichever one Windows picks (usually with the other PIN). Exclusive bind falls back to a random port.
    allow_reuse_address = os.name != "nt"


class Share:
    """Serve `payload` (UIGF JSON bytes) at GET /uigf to requests carrying the right X-PIN header."""
    # NOTE: plain HTTP, so someone sniffing the Wi-Fi could read the wish list (no cookies in it);
    # add TLS with a pinned self-signed cert if that ever matters.

    def __init__(self, payload: bytes, host="0.0.0.0"):
        self.pin = f"{secrets.randbelow(10 ** 6):06d}"
        self.bad = 0
        share = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/uigf":  # a browser poking the address (favicon, /) costs no PIN try
                    self.send_error(404)
                    return
                pin = self.headers.get("X-PIN", "").encode()
                if not hmac.compare_digest(pin, share.pin.encode()):
                    share.bad += 1
                    self.send_error(403)
                    if share.bad >= MAX_BAD_PINS:  # shutdown() waits for this handler, so not inline
                        threading.Thread(target=share.close).start()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        try:
            self.server = _Server((host, PORT), Handler)
        except OSError:
            self.server = _Server((host, 0), Handler)
        self.port = self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def pull(address: str, pin: str, timeout=15) -> dict:
    """Fetch the UIGF export from a PC's Share. `address` is "ip:port" as the PC shows it."""
    address = address.strip().removeprefix("http://").rstrip("/")
    if ":" not in address:  # typed the IP only
        address = f"{address}:{PORT}"
    req = urllib.request.Request(f"http://{address}/uigf", headers={"X-PIN": pin.strip()})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise SystemExit("Wrong PIN, or the PC stopped sharing.") from None
        raise
    except OSError as e:  # URLError, timeout, connection reset
        raise SystemExit(f"Could not reach {address}. Is the PC still sharing, on the same Wi-Fi?") from e
