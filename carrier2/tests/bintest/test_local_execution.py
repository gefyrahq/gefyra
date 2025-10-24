from multiprocessing import Process, Queue
import subprocess
import requests
from requests.adapters import HTTPAdapter, Retry
from time import sleep

CARRIER_TIMEOUT = 2


def test_a_cargo_tests():
    subprocess.run(
        "cargo test",
        shell=True,
    )


def test_b_test_upstreams(
    http_upstream, https_upstream, http_peer, https_peer_5443, https_peer_5444
):
    # this test ensures the local environment is not busy

    session = requests.Session()
    # http_upstream
    res = session.get(
        "http://localhost:4443",
    )
    assert res.status_code == 200

    # https_upstream
    res = session.get(
        "https://localhost:4444/",
        verify="./tests/fixtures/test_ca.pem",
    )
    assert res.status_code == 200

    # http_peer
    res = session.get(
        "http://localhost:5442/",
    )
    assert res.status_code == 200

    # https_peer_5443
    res = session.get(
        "https://localhost:5443/gefyra/",
        verify="./tests/fixtures/test_ca.pem",
    )
    assert res.status_code == 200

    # https_peer_5444
    res = session.get(
        "https://localhost:5444/gefyra/",
        verify="./tests/fixtures/test_ca.pem",
    )
    assert res.status_code == 200


def test_c_execute_help(carrier2):
    res = carrier2("--help")
    assert "Command-line options" in res


def test_d_noargs(carrier2):
    res = carrier2("")
    assert "Idle mode" in res


def test_e_simple_probes_upstream_all(carrier2, http_upstream):
    queue = Queue()
    # running carrier2 in a background process
    p = Process(
        target=carrier2,
        args=("-c ./tests/fixtures/default_upstream.yaml", CARRIER_TIMEOUT, queue),
    )
    p.start()

    retries = Retry(total=5, backoff_factor=0.2)
    session = requests.Session()
    # probe ports 8001,8002
    session.mount("http://localhost:8001", HTTPAdapter(max_retries=retries))
    session.mount("http://localhost:8002", HTTPAdapter(max_retries=retries))
    # cluster upstream
    session.mount("http://localhost:8080", HTTPAdapter(max_retries=retries))

    res = session.get("http://localhost:8001")
    assert res.status_code == 200

    res = session.get("http://localhost:8002")
    assert res.status_code == 200

    # this request gets upstreamed to http://localhost:4443
    res = session.get("http://localhost:8080")
    assert res.status_code == 200

    p.join()
    res = queue.get(timeout=1)
    assert "probe ports: [Number(8001), Number(8002)]" in res
    assert "Server starting" in res


def test_f_simple_probes_tls_upstream_all(carrier2, https_upstream):
    queue = Queue()
    # running carrier2 in a background process
    p = Process(
        target=carrier2,
        args=("-c ./tests/fixtures/default_upstream_tls.yaml", CARRIER_TIMEOUT, queue),
    )
    p.start()

    retries = Retry(total=5, backoff_factor=0.2)
    session = requests.Session()
    # probe ports 8001,8002
    session.mount("http://localhost:8001", HTTPAdapter(max_retries=retries))
    session.mount("http://localhost:8002", HTTPAdapter(max_retries=retries))
    # cluster upstream
    session.mount("https://localhost:8080", HTTPAdapter(max_retries=retries))

    res = session.get("http://localhost:8001")
    assert res.status_code == 200

    res = session.get("http://localhost:8002")
    assert res.status_code == 200

    # this request gets upstreamed to https://localhost:4443
    res = session.get("https://localhost:8080", verify="./tests/fixtures/test_ca.pem")
    assert res.status_code == 200
    assert "Gefyra upstream rockz!" in res.text

    res = session.get(
        "https://localhost:8080/what/a/path/", verify="./tests/fixtures/test_ca.pem"
    )
    assert res.status_code == 200
    assert "Gefyra upstream rockz!" in res.text

    p.join()
    res = queue.get(timeout=1)
    assert "Running with tls config" in res
    assert "Server starting" in res


def test_g_noprobes_one_peer(carrier2, http_upstream, http_peer):
    queue = Queue()
    # running carrier2 in a background process
    p = Process(
        target=carrier2,
        args=("-c ./tests/fixtures/one_peer.yaml", CARRIER_TIMEOUT, queue),
    )
    p.start()

    retries = Retry(total=5, backoff_factor=0.2)
    session = requests.Session()
    # cluster upstream
    session.mount("http://localhost:8080", HTTPAdapter(max_retries=retries))

    # this request gets upstreamed to https://localhost:4443
    res = session.get("http://localhost:8080")
    assert res.status_code == 200
    assert "Gefyra upstream rockz!" in res.text

    # this request gets dispatched to a peer on https://localhost:5443
    # rule: path match /what/a/path/
    res = session.get("http://localhost:8080/what/a/path/")
    assert res.status_code == 200
    assert "Gefyra peer rockz, too!" in res.text

    # this request gets dispatched to a peer on https://localhost:5443
    # rule: header match x-gefyra:peer
    res = session.get("http://localhost:8080/gefyra/", headers={"x-gefyra": "peer"})
    assert res.status_code == 200
    assert "Gefyra peer rockz, too!" in res.text

    # this request gets upstreamed to https://localhost:4443
    res = session.get("http://localhost:8080/gefyra/", headers={"x-gefyra": "upstream"})
    assert res.status_code == 200
    assert "Gefyra upstream rockz!" in res.text

    p.join()
    res = queue.get(timeout=1)
    assert "Server starting" in res


def test_h_probes_three_peer_mixed_https(
    carrier2, https_upstream, https_peer_5443, https_peer_5444, http_peer
):
    queue = Queue()
    # running carrier2 in a background process
    p = Process(
        target=carrier2,
        args=("-c ./tests/fixtures/three_peers_tls.yaml", CARRIER_TIMEOUT, queue),
    )
    p.start()

    retries = Retry(total=5, backoff_factor=0.2)
    session = requests.Session()
    # probe ports 8019, 8020, 8021
    session.mount("http://localhost:8019", HTTPAdapter(max_retries=retries))
    session.mount("http://localhost:8020", HTTPAdapter(max_retries=retries))
    session.mount("http://localhost:8021", HTTPAdapter(max_retries=retries))
    # cluster upstream
    session.mount("https://localhost:8080", HTTPAdapter(max_retries=retries))

    for req in [8019, 8020, 8021]:
        res = session.get(f"http://localhost:{req}")
        assert res.status_code == 200

    # this request gets upstreamed to https://localhost:4443
    res = session.get("https://localhost:8080", verify="./tests/fixtures/test_ca.pem")
    assert res.status_code == 200
    assert "Gefyra upstream rockz" in res.text

    res = session.get(
        "https://localhost:8080/what/a/path/", verify="./tests/fixtures/test_ca.pem"
    )
    assert res.status_code == 200
    assert "Gefyra upstream rockz" in res.text

    # this request gets dispatched to a peer on https://localhost:5443
    # rule: header match x-gefyra:user-1
    res = session.get(
        "https://localhost:8080/gefyra/",
        headers={"x-gefyra": "user-1"},
        verify="./tests/fixtures/test_ca.pem",
    )
    assert res.status_code == 200
    assert "Gefyra peer rockz, too!" in res.text

    # this request gets dispatched to a peer on https://localhost:5444
    # rule: header match x-gefyra:user-2
    res = session.get(
        "https://localhost:8080/gefyra/",
        headers={"x-gefyra": "user-2"},
        verify="./tests/fixtures/test_ca.pem",
    )
    assert res.status_code == 200
    assert "Gefyra peer with different output, here!" in res.text

    # this request gets dispatched to a peer on https://localhost:5442
    # (no tls for this client)
    # rule: header match x-gefyra:user-3
    res = session.get(
        "https://localhost:8080/gefyra/",
        headers={"x-gefyra": "user-3"},
        verify="./tests/fixtures/test_ca.pem",
    )
    assert res.status_code == 200
    assert "Gefyra peer rockz, too!" in res.text

    # this request gets upstreamed to https://localhost:4444
    res = session.get(
        "https://localhost:8080/gefyra/",
        headers={"x-gefyra": "upstream"},
        verify="./tests/fixtures/test_ca.pem",
    )

    assert res.status_code == 200
    assert "Gefyra upstream rockz!" in res.text

    p.join()
    res = queue.get(timeout=1)
    assert "Server starting" in res
