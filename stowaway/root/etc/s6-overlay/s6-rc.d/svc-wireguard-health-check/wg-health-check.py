#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from http.server import HTTPServer, BaseHTTPRequestHandler
from optparse import OptionParser
from os import popen

class HealthCheck(BaseHTTPRequestHandler):

    def do_GET(self):
        if check(self.server.device):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"healthy\n")
        else:
            self.send_error(404)

    def do_HEAD(self):
        self.do_GET()

def check(device):
    return popen("ip link show %s up " % device).read() != ""

def test(device):
    if check(device):
        print("%s up" % device)
    else:
        print("%s down" % device)

def main(port, device):
    server = HTTPServer(('', port), HealthCheck)
    server.device = device
    server.serve_forever()

def opts():
    parser = OptionParser(
        description="HTTP server that sends 204 response when device is up.")
    parser.add_option("-d", "--device", dest="device", default="wg0",
                      help="device name to check (default wg0)")
    parser.add_option("-p", "--port", dest="port", default=8080, type="int",
                      help="port on which to listen (default 8080)")
    parser.add_option("-t", "--test", action="store_true", dest="test", default=False,
                      help="show status and exit")
    return parser.parse_args()[0]

if __name__ == "__main__":
    options = opts()
    if options.test:
        test(options.device)
    else:
        main(options.port, options.device)