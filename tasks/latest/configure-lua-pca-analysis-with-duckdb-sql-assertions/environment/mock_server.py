import http.server
import socketserver
import sys
import os
import random

random.seed(int(os.environ.get("TB_VARIANT_SEED", "42")))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8888

class FlakyHandler(http.server.SimpleHTTPRequestHandler):
    request_count = 0

    def log_message(self, format, *args):
        pass # suppress logging

    def do_GET(self):
        # Flaky mock server: fail the first 3 requests
        if FlakyHandler.request_count < 3:
            FlakyHandler.request_count += 1
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"Service Unavailable")
            return
        super().do_GET()

os.chdir(os.path.dirname(os.path.abspath(__file__)))
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), FlakyHandler) as httpd:
    httpd.serve_forever()
