# Carrier2 - the next generation of HTTP(s) dispatcher for Gefyra (written in Rust)

## Gefyra Bridge Object
The Gefyra bridge object describes the dispatching configuration for Carrier2.
We always want a default upstream: the shaddow deployment created for a GefyraMount object.
Every Gefyra user bridge is subsequently added to Carrier2 to match certain HTTP attributes, for example
a header value or a path prefix. Matched traffic will be directed to the local Gefyra client container.


## Running the tests
The entire test suite (inlcuding Rust's `cargo test`) is set up with `pytest` and [pytest-kubernetes](https://github.com/Blueshoe/pytest-kubernetes). Run it under `/carrier2` with:
```bash
poetry run pytest -x
```

You will need the following dependencies installed:
- Docker
- Rust (`Rustup`)
- k3d
- Python + Poetry

### Example Config and Structure
```yaml
version: 1
threads: 2
pid_file: /tmp/carrier2.pid
error_log: /tmp/carrier.error.log
upgrade_sock: /tmp/carrier2.sock
upstream_keepalive_pool_size: 100
port: 8080
# tls:
#    certificate: "/path/to/ca.crt"
#    key: "/path/to/key.pem"
#    sni: "host.blueshoe.io"
clusterUpstream: 
    - "www.blueshoe.de:443"
probes: 
    httpGet:
        - 8001
        - 8002
bridges:
    user-1:
        endpoint: "www.blueshoe.io:443"
        tls: true
        sni: "www.blueshoe.io"
        rules:
            - match:
                - matchHeader:
                    name: "x-gefyra"
                    value: "user-1"
                # and
                - matchPath: 
                    path: "/my-svc"
                    type: "prefix"
            # or
            - match:
                - matchPath:
                    path: "/always"
                    type: "prefix"
```

## Run a dev version with debug ouput
`RUST_LOG=debug cargo run -- -c conf.yaml`


## Create a self-signed local certificate for testing
Found under `tests/fixtures`, `test_key.pem` and `test_cert.pem`.
Created with the following command:
```
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 365 -key ca.key -subj "/C=CN/ST=GD/L=SZ/O=Blueshoe/CN=Blueshoe CA" -out test_ca.pem
openssl req -newkey rsa:2048 -nodes -keyout test_key.pem -subj "/C=CN/ST=GD/L=SZ/O=Blueshoe/CN=localhost" -out server.csr
openssl x509 -req -extfile <(printf "subjectAltName=DNS:localhost") -days 365 -in server.csr -CA test_ca.pem -CAkey ca.key -CAcreateserial -out test_cert.pem
```

## Graceful Upgrade

### Manually
A graceful upgrade is performed with (in a buybox container):
```
kill -SIGQUIT $(ps | grep "[c]arrier2" | awk ' { print $1 }' | tail -1) && carrier2 -c /tmp/config.yaml -u &
```

1. Sending `SIGQUIT` to the currently running instance
2. Start a new instance

### Via Python
Have a look into `tests/integration/utils.py` to see how we send a new `Carrier2` config and perform a graceful reload.