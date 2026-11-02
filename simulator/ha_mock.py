from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from datetime import datetime, timezone


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/states":
            body = [self.state()]
        elif self.path == "/api/states/sensor.kanca_temperature":
            body = self.state()
        else:
            self.send_error(404)
            return
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def state(self):
        return {"entity_id": "sensor.kanca_temperature", "state": "24.5", "attributes": {"unit_of_measurement": "°C"}, "last_updated": datetime.now(timezone.utc).isoformat()}

    def log_message(self, *_):
        pass


HTTPServer(("0.0.0.0", 8123), Handler).serve_forever()
