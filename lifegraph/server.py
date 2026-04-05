"""Local dev server — serves web/ files + /api/summary endpoint."""

import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from lifegraph.db import init_db

WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")


class LifeGraphHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.abspath(WEB_DIR), **kwargs)

    def do_POST(self):
        if self.path == "/api/summary":
            return self._handle_summary()
        self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _handle_summary(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            start = body.get("start")
            end = body.get("end")
            if not start or not end:
                self._json_response(400, {"error": "start and end required"})
                return

            from lifegraph.summarizer import generate_summary
            result = generate_summary(start, end)

            # Rebuild graph.json to include new summary
            self._rebuild_graph()

            self._json_response(200, {"summary": result})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def _rebuild_graph(self):
        """Rebuild graph.json so the frontend picks up the new summary."""
        try:
            from lifegraph.clusters import build_clustered_graph
            g = build_clustered_graph(min_edge_weight=2)
            path = os.path.join(os.path.abspath(WEB_DIR), "graph.json")
            with open(path, "w") as f:
                json.dump(g, f, indent=2)
        except Exception:
            pass  # non-critical

    def _json_response(self, code, data):
        self.send_response(code)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        # Quieter logs
        if "/api/" in (args[0] if args else ""):
            super().log_message(format, *args)


def main(port=8042):
    init_db()
    server = HTTPServer(("localhost", port), LifeGraphHandler)
    print(f"LifeGraph server running at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
