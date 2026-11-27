from unittest.mock import AsyncMock, Mock, PropertyMock

import pytest


@pytest.mark.parametrize("status", [0, 403, 404, 500])
async def test_failed_destination_probe_preserves_active_bridge(monkeypatch, status):
    import kubernetes as k8s
    from gefyra.bridgestate import GefyraBridge, GefyraBridgeObject
    from gefyra.configuration import OperatorConfiguration
    from gefyra.handler import bridges

    data = {
        "metadata": {"name": "test-bridge", "namespace": "gefyra"},
        "state": "ACTIVE",
        "provider": "carrier2",
        "connectionProvider": "stowaway",
        "client": "client-a",
        "target": "deploy/nginx",
        "destinationIP": "10.0.0.1",
        "portMappings": ["8080:80"],
    }
    obj = GefyraBridgeObject(data)
    obj._write_state = Mock()
    bridge = GefyraBridge(obj, OperatorConfiguration(), Mock(), initial="ACTIVE")
    provider = Mock()
    provider.destination_exists = AsyncMock(
        side_effect=k8s.client.ApiException(status=status)
    )
    monkeypatch.setattr(
        GefyraBridge, "connection_provider", PropertyMock(return_value=provider)
    )
    bridge.completed_transition = Mock(return_value="completed")
    bridge.send = AsyncMock()
    monkeypatch.setattr(bridges, "GefyraBridge", Mock(return_value=bridge))

    await bridges.bridge_reconcile(data, Mock())

    assert bridge.active.is_active
    provider.destination_exists.assert_awaited_once_with("client-a", "10.0.0.1", 8080)
    bridge.send.assert_not_awaited()
    obj._write_state.assert_not_called()
