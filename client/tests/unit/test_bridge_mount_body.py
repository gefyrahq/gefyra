import pytest
from gefyra.configuration import ClientConfiguration
from gefyra.local.mount import get_gbridgemount_body


def test_bridge_mount_body_generation():
    config = ClientConfiguration()
    body = get_gbridgemount_body(
        config=config,
        name="test-mount",
        target="test-target",
        target_namespace="test-namespace",
        target_container="test-container",
        tls_certificate="test-cert",
        tls_key="test-key",
        tls_sni="test-sni",
    )
    # check body structure
    assert body["apiVersion"] == "gefyra.dev/v1"
    assert body["kind"] == "gefyrabridgemount"
    assert body["metadata"]["name"] == "test-mount"
    assert body["metadata"]["namespace"] == config.NAMESPACE
    assert body["targetNamespace"] == "test-namespace"
    assert body["target"] == "test-target"
    assert body["targetContainer"] == "test-container"
    assert body["provider"] == "carrier2"
    assert body["providerParameter"]["tls"]["certificate"] == "test-cert"
    assert body["providerParameter"]["tls"]["key"] == "test-key"
    assert body["providerParameter"]["tls"]["sni"] == "test-sni"


def test_bridge_mount_body_generation_no_tls():
    config = ClientConfiguration()
    body = get_gbridgemount_body(
        config=config,
        name="test-mount",
        target="test-target",
        target_namespace="test-namespace",
        target_container="test-container",
    )
    # check body structure
    assert body["apiVersion"] == "gefyra.dev/v1"
    assert body["kind"] == "gefyrabridgemount"
    assert body["metadata"]["name"] == "test-mount"
    assert body["metadata"]["namespace"] == config.NAMESPACE
    assert body["targetNamespace"] == "test-namespace"
    assert body["target"] == "test-target"
    assert body["targetContainer"] == "test-container"
    assert body["provider"] == "carrier2"
    assert "tls" not in body["providerParameter"]


def test_bridge_mount_body_generation_invalid_tls():
    config = ClientConfiguration()
    with pytest.raises(RuntimeError) as excinfo:
        get_gbridgemount_body(
            config=config,
            name="test-mount",
            target="test-target",
            target_namespace="test-namespace",
            target_container="test-container",
            tls_key="test-key",
        )
    assert (
        str(excinfo.value)
        == "TLS configuration requires both certificate and key to be set."
    )
    with pytest.raises(RuntimeError) as excinfo:
        get_gbridgemount_body(
            config=config,
            name="test-mount",
            target="test-target",
            target_namespace="test-namespace",
            target_container="test-container",
            tls_certificate="test-cert",
        )
    assert (
        str(excinfo.value)
        == "TLS configuration requires both certificate and key to be set."
    )
