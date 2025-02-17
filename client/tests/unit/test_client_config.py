import json
from gefyra.types import GefyraClientConfig


def test_read_client_config():
    payload = {
        "client_id": "client-a",
        "kubernetes_server": "https://gefyra.dev",
        "provider": "stowaway",
        "token": "some-token",
        "namespace": "my_ms",
        "ca_crt": "ca_cert",
        "gefyra_server": "https://gefyra.dev",
        "registry": "https://quay.io",
        "wireguard_mtu": 1320,
    }
    GefyraClientConfig.from_json_str(json.dumps(payload))


def test_read_client_config_optionals_missing():
    payload = {
        "client_id": "client-a",
        "kubernetes_server": "https://gefyra.dev",
        "provider": "stowaway",
        "token": "some-token",
        "namespace": "my_ms",
        "ca_crt": "ca_cert",
        "gefyra_server": "https://gefyra.dev",
    }
    GefyraClientConfig.from_json_str(json.dumps(payload))
