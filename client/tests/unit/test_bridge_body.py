from gefyra.types.bridge import GefyraBridge
from gefyra.configuration import ClientConfiguration


def test_bridge_body_generation():
    config = ClientConfiguration()
    body = GefyraBridge(
        name="test-bridge",
        target="nginx-deployment-default-1234",
        client="client-a",
        local_container_ip="192.178.0.22",
        port_mappings="8080:8080",
    ).get_k8s_bridge_body(config)
    # check body structure
    assert body["apiVersion"] == "gefyra.dev/v1"
    assert body["kind"] == "gefyrabridge"
    assert body["metadata"]["name"] == "test-bridge"
    assert body["metadata"]["namespace"] == config.NAMESPACE
    assert body["targetNamespace"] == ""
    assert body["target"] == "nginx-deployment-default-1234"
    assert body["provider"] == "carrier2"
