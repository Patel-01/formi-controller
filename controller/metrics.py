"""
C14: Loop observability — Prometheus-style /metrics endpoint.

Starts a background HTTP server on the port given to MetricsServer.start().
Default port: 8711.

Gauges emitted (Prometheus text format):
  formi_ingest_lag_events     – events behind latest chunk
  formi_credits_remaining     – credits left per /sim/state
  formi_decisions_per_hour    – proposals submitted in the last 60 sim-minutes
  formi_active_experiments    – open experiments across all workflows
  formi_winners_applied       – cumulative winners promoted since start
  formi_hallucination_rate    – hallucination flag rate in last 100 connected calls
  formi_tick_duration_seconds – wall-clock time of the last tick
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

log = logging.getLogger(__name__)

_registry: dict[str, float] = {}
_lock = threading.Lock()


def record(name: str, value: float) -> None:
    with _lock:
        _registry[name] = value


def _build_response(db_path: str) -> str:
    lines: list[str] = ["# TYPE formi_gauge gauge"]

    # Pull live values straight from the database — no in-process cache needed
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        active = conn.execute(
            "SELECT COUNT(*) AS n FROM experiments WHERE status='active'"
        ).fetchone()["n"]
        lines.append(f"formi_active_experiments {active}")

        won = conn.execute(
            "SELECT COUNT(*) AS n FROM experiments WHERE status='done'"
        ).fetchone()["n"]
        lines.append(f"formi_winners_applied {won}")

        # Hallucination rate — last 100 connected calls across all workflows
        row = conn.execute("""
            SELECT SUM(hallucination_flag) AS flags, COUNT(*) AS n
            FROM (SELECT hallucination_flag FROM calls
                  WHERE connected=1 ORDER BY rowid DESC LIMIT 100)
        """).fetchone()
        if row and row["n"]:
            lines.append(f"formi_hallucination_rate {row['flags'] / row['n']:.4f}")
        else:
            lines.append("formi_hallucination_rate 0")

        # Proposals submitted in the last sim-hour (approximated by ts ordering)
        recent = conn.execute("""
            SELECT COUNT(*) AS n FROM proposals
            WHERE submitted_ts >= datetime('now', '-1 hour')
        """).fetchone()["n"]
        lines.append(f"formi_decisions_per_hour {recent}")

        conn.close()
    except Exception as exc:
        log.debug("metrics db read error: %s", exc)

    # In-process gauges (latency, credits, ingest lag)
    with _lock:
        for name, value in _registry.items():
            lines.append(f"{name} {value:.4f}")

    return "\n".join(lines) + "\n"


class _Handler(BaseHTTPRequestHandler):
    db_path: str = "controller.db"

    def do_GET(self):  # noqa: N802
        if self.path in ("/metrics", "/health"):
            body = _build_response(self.db_path).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):  # silence request logs
        pass


class MetricsServer:
    def __init__(self, db_path: str = "controller.db", port: int = 8711):
        self.db_path = db_path
        self.port = port
        self._server: HTTPServer | None = None

    def start(self) -> None:
        _Handler.db_path = self.db_path

        def _serve():
            self._server = HTTPServer(("0.0.0.0", self.port), _Handler)
            log.info("Metrics server on :%d  (GET /metrics)", self.port)
            self._server.serve_forever()

        t = threading.Thread(target=_serve, daemon=True, name="metrics-http")
        t.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
