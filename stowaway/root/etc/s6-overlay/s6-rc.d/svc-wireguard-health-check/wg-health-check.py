#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess

class HealthCheck(BaseHTTPRequestHandler):

    def do_GET(self) -> None:
        if check():
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"healthy\n")
        else:
            self.send_error(404)

    def do_HEAD(self) -> None:
        self.do_GET()

def check() -> bool:
    try:
        subprocess.check_call("wg | grep 'listening port: 51820'", shell=True)
        return True
    except subprocess.CalledProcessError:
        return False

def main(port) -> None:
    server = HTTPServer(('0.0.0.0', port), HealthCheck)
    server.serve_forever()

if __name__ == "__main__":
    main(51822)