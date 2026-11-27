from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, PropertyMock

import pytest


@pytest.mark.parametrize(
    ("operation", "state"),
    [
        ("delete", "ENABLING"),
        ("delete", "DISABLING"),
        ("disable", "ACTIVE"),
        ("disable", "DISABLING"),
    ],
)
async def test_handler_retries_cleanup_after_configmap_write(
    monkeypatch, operation, state
):
    import gefyra.clientstate as clientstate
    import gefyra.connection.stowaway as stowaway
    from gefyra.handler import clients

    configuration = clientstate.OperatorConfiguration()
    provider = stowaway.Stowaway(configuration, Mock())
    peer_id = "client-a"
    peer_name = provider._translate_peer_name(peer_id)
    configmap = stowaway.k8s.client.V1ConfigMap(
        metadata=stowaway.k8s.client.V1ObjectMeta(
            name="gefyra-stowaway-config", namespace=configuration.NAMESPACE
        ),
        data={
            "PEERS": f"{peer_name},other",
            f"SERVER_ALLOWEDIPS_PEER_{peer_name}": "10.0.0.0/24",
        },
    )
    api = Mock()
    api.read_namespaced_config_map.side_effect = lambda *args: deepcopy(configmap)

    def replace_configmap(*, name, namespace, body):
        configmap.data = deepcopy(body.data)

    api.replace_namespaced_config_map.side_effect = replace_configmap
    monkeypatch.setattr(stowaway, "core_v1_api", api)
    provider._get_stowaway_pod = AsyncMock(
        return_value=SimpleNamespace(
            metadata=SimpleNamespace(
                name="stowaway-0", namespace=configuration.NAMESPACE
            )
        )
    )
    monkeypatch.setattr(stowaway.asyncio, "sleep", AsyncMock())

    error = stowaway.k8s.client.ApiException(status=0, reason="exec failed")
    runtime_peer_exists = True
    cleanup_order = []

    def exec_command(api_instance, pod, namespace, container, command):
        nonlocal runtime_peer_exists
        # Both attempts must reach runtime cleanup after the declaration is gone.
        assert peer_name not in configmap.data["PEERS"].split(",")
        assert command == ["rm", "-rf", f"/config/peer_{peer_name}"]
        if exec_mock.call_count == 1:
            raise error
        runtime_peer_exists = False
        cleanup_order.append("runtime")
        return ""

    exec_mock = Mock(side_effect=exec_command)
    monkeypatch.setattr(stowaway, "exec_command_pod", exec_mock)

    async def restart():
        assert not runtime_peer_exists
        cleanup_order.append("restart")

    provider._restart_stowaway = AsyncMock(side_effect=restart)
    monkeypatch.setattr(
        clientstate.GefyraClient,
        "connection_provider",
        PropertyMock(return_value=provider),
    )
    monkeypatch.setattr(clientstate.GefyraClient, "post_event", AsyncMock())
    delete_sa = AsyncMock()
    cleanup_bridges = AsyncMock()
    monkeypatch.setattr(
        clientstate, "handle_delete_gefyraclient_serviceaccount", delete_sa
    )
    monkeypatch.setattr(
        clientstate.GefyraClient, "cleanup_all_bridges", cleanup_bridges
    )

    data = {
        "metadata": {"name": peer_id, "namespace": configuration.NAMESPACE},
        "state": state,
        "provider": "stowaway",
        "providerConfig": {"Interface.Address": "10.0.0.2"},
    }
    custom_api = Mock()

    def patch_client(**kwargs):
        data.update(deepcopy(kwargs["body"]))

    custom_api.patch_namespaced_custom_object.side_effect = patch_client
    monkeypatch.setattr(
        clientstate.k8s.client, "CustomObjectsApi", Mock(return_value=custom_api)
    )

    async def handle():
        # Kopf constructs a new state machine from the persisted body on retry.
        body = deepcopy(data)
        if operation == "delete":
            return await clients.client_deleted(body, Mock())
        return await clients.client_connection_changed(None, body, Mock())

    with pytest.raises(stowaway.k8s.client.ApiException) as raised:
        await handle()
    assert raised.value is error
    assert configmap.data == {"PEERS": "other"}
    assert not await provider.peer_exists(peer_id)
    assert runtime_peer_exists
    provider._restart_stowaway.assert_not_awaited()
    delete_sa.assert_not_awaited()
    assert data["providerConfig"] == {"Interface.Address": "10.0.0.2"}

    await handle()

    assert not runtime_peer_exists
    assert exec_mock.call_count == 2
    api.replace_namespaced_config_map.assert_called_once()
    provider._restart_stowaway.assert_awaited_once()
    assert cleanup_order == ["runtime", "restart"]
    if operation == "delete":
        delete_sa.assert_awaited_once()
        cleanup_bridges.assert_awaited_once()
    else:
        assert data["state"] == "WAITING"
        assert data["providerConfig"] is None
        assert data["status"]["wireguard"] is None
