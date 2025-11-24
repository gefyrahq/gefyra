#!/bin/env python

import http.server
import ssl
import signal
import socket
import socketserver
import sys
from datetime import datetime
import threading

if sys.argv[1:]:
    port = int(sys.argv[1])
    port_ssl = int(sys.argv[2])
else:
    port = 8000
    port_ssl = 9000


class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    default_request_version = "HTTP/1.1"

    def do_GET(self):
        hostname = socket.gethostname()
        now = datetime.utcnow()
        content = bytes(
            f"<html><body><h1>Hello from Gefyra. It is {now} on"
            f" {hostname}.</h1></body></html>".encode("utf-8")
        )
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


class MyHttpsRequestHandler(http.server.SimpleHTTPRequestHandler):
    default_request_version = "HTTP/1.1"

    def do_GET(self):
        hostname = socket.gethostname()
        now = datetime.utcnow()
        content = bytes(
            f"<html><body><h1>Hello from Gefyra over TLS. It is {now} on"
            f" {hostname}.</h1></body></html>".encode("utf-8")
        )
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


my_handler = MyHttpRequestHandler
server = socketserver.ThreadingTCPServer(("0.0.0.0", port), my_handler)

my_tls_handler = MyHttpsRequestHandler
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.check_hostname = False
context.load_cert_chain("/tmp/client-cert.pem", "/tmp/client-key.pem")

ssl_server = socketserver.ThreadingTCPServer(("0.0.0.0", port_ssl), my_tls_handler)
ssl_server.socket = context.wrap_socket(ssl_server.socket, server_side=True)

def signal_handler(signal, frame):
    try:
        if server:
            server.server_close()
        if ssl_server:
            ssl_server.close()
    finally:
        sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
try:
    sys.stdout.flush()
    print("Starting HTTP Server")
    http = threading.Thread(target=server.serve_forever)
    http.start()
    print("Starting HTTPS Server")
    https = threading.Thread(target=ssl_server.serve_forever)
    https.start()
    http.join()
except KeyboardInterrupt:
    pass

server.server_close()
ssl_server.server_close()
