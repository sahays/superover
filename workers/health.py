"""
Lightweight health-check HTTP server for Cloud Run workers.
Runs in a daemon thread so it doesn't block the main poll loop.
"""

import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    """Responds to GET /health with 200."""

    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default stderr logging to avoid noise
        pass


def start_health_server():
    """Start the health-check HTTP server on PORT (default 8080) in a daemon thread."""
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health-check server started on port {port}")
