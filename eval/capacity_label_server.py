"""A local page for labeling the M4 capacity panel (decision Item 107). Standard library only; localhost only.

    PYTHONPATH=. python -m eval.capacity_label_server --evidence <evidence.json> [--port 8031]

Serves ``eval/capacity_label_page.html``, the panel (``eval/capacity_label_panel.json``) with its evidence, and
saves each label as it is made to ``eval/results/2026-11-11-m4/labels.json`` (written whole, atomically).
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

PAGE = Path(__file__).with_name("capacity_label_page.html")
PANEL = Path("eval/capacity_label_panel.json")
LABELS = Path("eval/results/2026-11-11-m4/labels.json")
_lock = Lock()


def _read_labels() -> dict:
    return json.loads(LABELS.read_text()) if LABELS.exists() else {}


def _write_labels(labels: dict) -> None:
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=LABELS.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(labels, f, indent=1, sort_keys=True)
    os.replace(tmp, LABELS)


def make_handler(evidence_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/data":
                body = {"panel": json.loads(PANEL.read_text()), "evidence": json.loads(evidence_path.read_text()),
                        "labels": _read_labels()}
                self._send(200, json.dumps(body).encode(), "application/json")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):  # noqa: N802
            if self.path != "/label":
                self._send(404, b"not found", "text/plain")
                return
            n = int(self.headers.get("Content-Length") or 0)
            label = json.loads(self.rfile.read(n))
            pin = label.get("pin")
            if not isinstance(pin, str):
                self._send(400, b"pin required", "text/plain")
                return
            with _lock:
                labels = _read_labels()
                labels[pin] = label
                _write_labels(labels)
            self._send(200, json.dumps({"saved": pin, "count": len(labels)}).encode(), "application/json")

        def log_message(self, *args):  # quiet
            pass

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--port", type=int, default=8031)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.evidence))
    print(f"labeling page on http://localhost:{args.port}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
