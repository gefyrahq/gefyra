import pytest
from gefyra.configuration import ClientConfiguration
from gefyra.local.mount import get_gbridgemount_body


def test_bridge_mount_body_generation_secret_notation():
    config = ClientConfiguration()
    body = get_gbridgemount_body(
        config=config,
        name="test-mount",
        target="test-target",
        target_namespace="test-namespace",
        target_container="test-container",
        tls_certificate=["secret:myns/mycert:cert.pem@443"],
        tls_key=["secret:mykey:key.pem@443"],
        provider="carrier2mount",
    )

    assert body["providerParameter"][443]["tls"]["certificate"] == {
        "secret": {"namespace": "myns", "name": "mycert", "key": "cert.pem"}
    }
    assert body["providerParameter"][443]["tls"]["key"] == {
        "secret": {"namespace": "default", "name": "mykey", "key": "key.pem"}
    }


def test_bridge_mount_body_generation_secret_notation_no_port():
    config = ClientConfiguration()
    body = get_gbridgemount_body(
        config=config,
        name="test-mount",
        target="test-target",
        target_namespace="test-namespace",
        target_container="test-container",
        tls_certificate=["secret:myns/mycert:cert.pem"],
        tls_key=["secret:mykey:key.pem"],
        provider="carrier2mount",
    )

    assert body["providerParameter"]["tls"]["certificate"] == {
        "secret": {"namespace": "myns", "name": "mycert", "key": "cert.pem"}
    }
    assert body["providerParameter"]["tls"]["key"] == {
        "secret": {"namespace": "default", "name": "mykey", "key": "key.pem"}
    }


def test_bridge_mount_body_generation_invalid_secret_notation():
    config = ClientConfiguration()

    # Missing key
    with pytest.raises(ValueError) as excinfo:
        get_gbridgemount_body(
            config=config,
            name="test-mount",
            target="test-target",
            target_namespace="test-namespace",
            target_container="test-container",
            tls_certificate=["secret:mycert@443"],
            tls_key=["secret:mykey@443"],
            provider="carrier2mount",
        )
    assert "Invalid secret notation" in str(excinfo.value)
    assert "Missing key" in str(excinfo.value) or "Expected format" in str(
        excinfo.value
    )

    # Missing secret name
    with pytest.raises(ValueError) as excinfo:
        get_gbridgemount_body(
            config=config,
            name="test-mount",
            target="test-target",
            target_namespace="test-namespace",
            target_container="test-container",
            tls_certificate=["secret::cert.pem"],
            tls_key=["secret:mykey:key.pem"],
            provider="carrier2mount",
        )
    assert "Missing secret name" in str(excinfo.value)

    # Empty namespace (should default to default or be handled)
    body = get_gbridgemount_body(
        config=config,
        name="test-mount",
        target="test-target",
        target_namespace="test-namespace",
        target_container="test-container",
        tls_certificate=["secret:/mycert:cert.pem"],
        tls_key=["secret:mykey:key.pem"],
        provider="carrier2mount",
    )
    assert (
        body["providerParameter"]["tls"]["certificate"]["secret"]["namespace"]
        == "default"
    )


def test_bridge_mount_body_generation_sni_secret_notation():
    config = ClientConfiguration()
    body = get_gbridgemount_body(
        config=config,
        name="test-mount",
        target="test-target",
        target_namespace="test-namespace",
        target_container="test-container",
        tls_certificate=["cert.pem"],
        tls_key=["key.pem"],
        tls_sni=["secret:myns/mysni:sni.txt"],
        provider="carrier2mount",
    )

    assert body["providerParameter"]["tls"]["sni"] == {
        "secret": {"namespace": "myns", "name": "mysni", "key": "sni.txt"}
    }


def test_bridge_mount_body_generation_path_notation_intact():
    config = ClientConfiguration()
    # Verify that standard paths still work
    body = get_gbridgemount_body(
        config=config,
        name="test-mount",
        target="test-target",
        target_namespace="test-namespace",
        target_container="test-container",
        tls_certificate=["/path/to/cert.pem@443"],
        tls_key=["/path/to/key.pem@443"],
        provider="carrier2mount",
    )

    assert body["providerParameter"][443]["tls"]["certificate"] == "/path/to/cert.pem"
    assert body["providerParameter"][443]["tls"]["key"] == "/path/to/key.pem"

    # Global path
    body = get_gbridgemount_body(
        config=config,
        name="test-mount",
        target="test-target",
        target_namespace="test-namespace",
        target_container="test-container",
        tls_certificate=["/path/to/cert.pem"],
        tls_key=["/path/to/key.pem"],
        provider="carrier2mount",
    )
    assert body["providerParameter"]["tls"]["certificate"] == "/path/to/cert.pem"
    assert body["providerParameter"]["tls"]["key"] == "/path/to/key.pem"
