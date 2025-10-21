import multiprocessing
import os
import signal
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
import ssl
from typing import Optional
import pytest


@pytest.fixture(scope="session")
def carrier_binary(request):
    name = "RUST_LOG=debug ./target/release/carrier2"
    subprocess.run(
        (f"cargo build --release"),
        shell=True,
    )
    yield name


@pytest.fixture
def carrier2(carrier_binary):

    def call_with_args(
        args: str, timeout: int = 1, queue: Optional[multiprocessing.Queue] = None
    ) -> str:
        try:
            p = subprocess.Popen(
                f"{carrier_binary} {args}",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            p.wait(timeout=timeout)
            stdout = p.stdout.read().decode("utf-8")
            if queue:
                queue.put(stdout)
            else:
                return stdout
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            stdout = p.stdout.read().decode("utf-8")
            if queue:
                queue.put(stdout)
            else:
                return stdout

    yield call_with_args


# this is the test upstream, modify for more sophisticated test cases
class UpstreamRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        request_path = self.path
        self.send_response(200)
        self.end_headers()
        self.wfile.write("Gefyra upstream rockz!".encode("utf-8"))

    def log_message(self, *args, **kwargs):
        print("Upstream request")


# this is a Gefyra client peer
class PeerRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        request_path = self.path
        self.send_response(200)
        self.end_headers()
        self.wfile.write("Gefyra peer rockz, too!".encode("utf-8"))

    def log_message(self, *args, **kwargs):
        print("Peer1 request")


# this is another Gefyra client peer
class Peer2RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        request_path = self.path
        self.send_response(200)
        self.end_headers()
        self.wfile.write("Gefyra peer with different output, here!".encode("utf-8"))

    def log_message(self, *args, **kwargs):
        print("Peer2 request")


def serve(
    handler=UpstreamRequestHandler,
    port: int = 4443,
    tls_keypath: Optional[str] = None,
    tls_certpath: Optional[str] = None,
):
    httpd = HTTPServer(("localhost", port), handler)
    if tls_keypath and tls_certpath:
        httpd.socket = ssl.wrap_socket(
            httpd.socket, keyfile=tls_keypath, certfile=tls_certpath, server_side=True
        )
    httpd.serve_forever()


@pytest.fixture
def http_upstream(request):
    p = multiprocessing.Process(target=serve)
    p.start()
    yield
    os.kill(p.pid, signal.SIGKILL)


@pytest.fixture
def https_upstream(request):
    p = multiprocessing.Process(
        target=serve,
        args=(
            UpstreamRequestHandler,
            4444,
            "./tests/fixtures/test_key.pem",
            "./tests/fixtures/test_cert.pem",
        ),
    )
    p.start()
    yield
    os.kill(p.pid, signal.SIGKILL)


@pytest.fixture
def http_peer(request):
    p = multiprocessing.Process(
        target=serve,
        args=(
            PeerRequestHandler,
            5442,
        ),
    )
    p.start()
    yield
    os.kill(p.pid, signal.SIGKILL)


@pytest.fixture
def https_peer_5443(request):
    p = multiprocessing.Process(
        target=serve,
        args=(
            PeerRequestHandler,
            5443,
            "./tests/fixtures/test_key.pem",
            "./tests/fixtures/test_cert.pem",
        ),
    )
    p.start()
    yield
    os.kill(p.pid, signal.SIGKILL)


@pytest.fixture
def https_peer_5444(request):
    p = multiprocessing.Process(
        target=serve,
        args=(
            Peer2RequestHandler,
            5444,
            "./tests/fixtures/test_key.pem",
            "./tests/fixtures/test_cert.pem",
        ),
    )
    p.start()
    yield
    os.kill(p.pid, signal.SIGKILL)
