from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def stowaway(monkeypatch):
    import gefyra.connection.stowaway as module

    provider = module.Stowaway(SimpleNamespace(NAMESPACE="gefyra"), Mock())
    api = Mock()
    monkeypatch.setattr(module, "core_v1_api", api)
    monkeypatch.setattr(module.asyncio, "sleep", AsyncMock())
    return module, provider, api


@pytest.mark.parametrize("status", [0, 403, 404, 500])
@pytest.mark.parametrize(
    "operation", ["peer", "destination_service", "destination_config", "add", "remove"]
)
async def test_api_errors_propagate(stowaway, status, operation):
    module, provider, api = stowaway
    error = module.k8s.client.ApiException(status=status, reason="lookup failed")
    api.read_namespaced_config_map.side_effect = error
    api.list_namespaced_service.return_value = SimpleNamespace(items=[Mock()])
    if operation == "peer":
        call = provider.get_peer_config("client-a")
    elif operation.startswith("destination"):
        if operation == "destination_service":
            api.list_namespaced_service.side_effect = error
        call = provider.destination_exists("client-a", "10.0.0.1", 8080)
    else:
        provider._edit_peer_configmap = AsyncMock(side_effect=error)
        call = getattr(provider, f"{operation}_peer")("client-a")
    with pytest.raises(module.k8s.client.ApiException) as raised:
        await call
    assert raised.value is error


async def test_absence_after_successful_lookup(stowaway):
    _, provider, api = stowaway
    api.read_namespaced_config_map.return_value = SimpleNamespace(
        data={"PEERS": "other"}
    )
    assert not await provider.peer_exists("client-a")
    api.list_namespaced_service.return_value = SimpleNamespace(items=[])
    assert not await provider.destination_exists("client-a", "10.0.0.1", 8080)


async def test_remove_peer_retries_runtime_cleanup_without_declaration(
    stowaway, monkeypatch
):
    module, provider, api = stowaway
    api.read_namespaced_config_map.return_value = SimpleNamespace(data={"PEERS": ""})
    provider._get_stowaway_pod = AsyncMock(
        return_value=SimpleNamespace(
            metadata=SimpleNamespace(name="stowaway-0", namespace="gefyra")
        )
    )
    provider._restart_stowaway = AsyncMock()
    provider._peer_runtime_exists = AsyncMock(return_value=True)
    error = module.k8s.client.ApiException(status=0, reason="exec failed")
    exec_command = Mock(side_effect=[error, ""])
    monkeypatch.setattr(module, "exec_command_pod", exec_command)
    with pytest.raises(module.k8s.client.ApiException):
        await provider.remove_peer("client-a")
    assert await provider.remove_peer("client-a")
    assert exec_command.call_count == 2
    provider._restart_stowaway.assert_awaited_once()


async def test_remove_peer_requires_runtime_cleanup(stowaway):
    _, provider, api = stowaway
    api.read_namespaced_config_map.return_value = SimpleNamespace(data={"PEERS": ""})
    provider._get_stowaway_pod = AsyncMock(return_value=None)
    with pytest.raises(RuntimeError, match="No Stowaway Pod"):
        await provider.remove_peer("client-a")
