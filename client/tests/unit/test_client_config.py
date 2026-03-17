import json
from unittest.mock import patch

from gefyra.api.clients import write_client_file
from gefyra.local.cargo import create_wireguard_config
from gefyra.types import GefyraClient, GefyraClientConfig
from gefyra.types.stowaway import StowawayConfig


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


def test_read_client_config_no_service_account():
    payload = {
        "client_id": "client-a",
        "kubernetes_server": "https://gefyra.dev",
        "provider": "stowaway",
        "namespace": "my_ms",
        "gefyra_server": "https://gefyra.dev",
    }
    GefyraClientConfig.from_json_str(json.dumps(payload))


@patch("gefyra.api.clients.ClientConfiguration")
@patch("gefyra.api.clients.get_client")
def test_client_config_write_with_sa(mock_get_client, mock_client_config):
    mock_get_client.return_value = GefyraClient(
        {
            "metadata": {"name": "client-a", "namespace": "gefyra", "uid": "12345"},
            "client_id": "client-a",
            "serviceAccountData": {"token": "some-token", "ca.crt": "ca_cert"},
        },
        mock_client_config,
    )
    mock_client_config.KUBE_CONFIG_FILE.return_value = "test"
    mock_client_config.KUBE_CONTEXT.return_value = "test"
    mock_client_config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object.return_value = {
        "metadata": {"name": "client-a", "namespace": "gefyra", "uid": "12345"},
        "client_id": "client-a",
    }
    mock_client_config.get_kubernetes_api_url.return_value = "https://gefyra.dev"
    mock_client_config.return_value.get_stowaway_host.return_value = (
        "https://gefyra.dev"
    )
    result = write_client_file("client-a")

    result = json.loads(result)
    assert result["ca_crt"] == "ca_cert"
    assert result["token"] == "some-token"


@patch("gefyra.api.clients.ClientConfiguration")
@patch("gefyra.api.clients.get_client")
def test_client_config_write_without_sa(mock_get_client, mock_client_config):
    mock_get_client.return_value = GefyraClient(
        {
            "metadata": {"name": "client-a", "namespace": "gefyra", "uid": "12345"},
            "client_id": "client-a",
        },
        mock_client_config,
    )
    mock_client_config.KUBE_CONFIG_FILE.return_value = "test"
    mock_client_config.KUBE_CONTEXT.return_value = "test"
    mock_client_config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object.return_value = {
        "metadata": {"name": "client-a", "namespace": "gefyra", "uid": "12345"},
        "client_id": "client-a",
    }
    mock_client_config.get_kubernetes_api_url.return_value = "https://gefyra.dev"
    mock_client_config.return_value.get_stowaway_host.return_value = (
        "https://gefyra.dev"
    )
    result = write_client_file("client-a")

    result = json.loads(result)

    assert result["ca_crt"] is None
    assert result["token"] is None


def _make_stowaway_config():
    return StowawayConfig(
        iaddress="192.168.99.2/32",
        idns="192.168.99.1",
        iport="51820",
        iprivatekey="fakeprivkey=",
        pallowedips="0.0.0.0/0",
        pendpoint="1.2.3.4:31820",
        ppublickey="fakepubkey=",
        presharedkey="fakepsk=",
    )


def test_wireguard_config_without_mtu():
    """When mtu is None, the MTU line should be omitted from WireGuard config"""
    params = _make_stowaway_config()
    config = create_wireguard_config(params, "1.2.3.4:31820", mtu=None)
    assert "MTU" not in config
    assert "[Interface]" in config
    assert "PrivateKey = fakeprivkey=" in config


def test_wireguard_config_with_explicit_mtu():
    """When mtu is set, the MTU line should appear in WireGuard config"""
    params = _make_stowaway_config()
    config = create_wireguard_config(params, "1.2.3.4:31820", mtu="1200")
    assert "MTU = 1200" in config


def test_wireguard_config_default_mtu_is_none():
    """Default mtu parameter should be None (auto-detect)"""
    params = _make_stowaway_config()
    config = create_wireguard_config(params, "1.2.3.4:31820")
    assert "MTU" not in config


def test_client_config_default_mtu_is_none():
    """GefyraClientConfig should default wireguard_mtu to None"""
    config = GefyraClientConfig(
        client_id="test",
        kubernetes_server="https://example.com",
        provider="stowaway",
        namespace="gefyra",
        gefyra_server="1.2.3.4:31820",
    )
    assert config.wireguard_mtu is None
    data = json.loads(config.json)
    assert data["wireguard_mtu"] is None
