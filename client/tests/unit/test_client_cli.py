import pytest
from unittest.mock import patch

from gefyra.api.clients import add_clients, list_client


def test_add_client_invalid_param():
    with pytest.raises(RuntimeError) as exc_info:
        add_clients(client_id="client-a", quantity=2)
    assert "Cannot specify both quantity > 1 and client_id" in str(exc_info.value)


@patch("gefyra.api.clients.handle_create_gefyraclient")
def test_create_multiple_clients(mock):

    clients = add_clients(client_id="", quantity=3, registry="kuchen.io/gefyra")

    assert mock.call_count == 3
    assert len(clients) == 3


@patch("gefyra.api.clients.ClientConfiguration")
def test_list_clients(mock):
    instance = mock.return_value
    instance.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = {
        "items": [
            {
                "metadata": {
                    "name": "client-a",
                    "namespace": "default",
                    "uid": "12345",
                    "labels": {"app": "gefyra"},
                },
                "provider": "kubernetes",
            },
            {
                "metadata": {
                    "name": "client-b",
                    "namespace": "default",
                    "uid": "67890",
                    "labels": {"app": "gefyra"},
                },
                "provider": "kubernetes",
            },
        ]
    }

    clients = list_client()
    assert len(clients) == 2
    assert clients[0].namespace == "default"
    assert clients[0].uid == "12345"
    assert clients[0].provider == "kubernetes"
    assert clients[0].client_id == "client-a"
    assert clients[1].client_id == "client-b"
    assert clients[1].namespace == "default"
    assert clients[1].uid == "67890"
    assert clients[1].provider == "kubernetes"
