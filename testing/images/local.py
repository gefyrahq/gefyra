#!/bin/env python

import http.server
import signal
import socket
import socketserver
import sys
from datetime import datetime

if sys.argv[1:]:
    port = int(sys.argv[1])
else:
    port = 8000


class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        hostname = socket.gethostname()
        now = datetime.utcnow()
        self.wfile.write(
            bytes(f"<html><body><h1>Hello from Gefyra. It is {now} on {hostname}.</h1></body></html>".encode("utf-8"))
        )


my_handler = MyHttpRequestHandler
server = socketserver.ThreadingTCPServer(("", port), my_handler)


def signal_handler(signal, frame):
    try:
        if server:
            server.server_close()
    finally:
        sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
try:
    while True:
        sys.stdout.flush()
        server.serve_forever()
except KeyboardInterrupt:
    pass

server.server_close()
