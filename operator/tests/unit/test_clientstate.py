from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest


@pytest.fixture
def make_client(monkeypatch):
    import gefyra.clientstate as module

    provider = Mock()
    provider.remove_peer = AsyncMock()
    provider.peer_exists = AsyncMock(return_value=False)
    provider.add_peer = AsyncMock()
    provider.get_peer_config = AsyncMock(return_value={"Interface.Address": "10.0.0.2"})
    monkeypatch.setattr(
        module.GefyraClient, "connection_provider", PropertyMock(return_value=provider)
    )
    delete_sa = AsyncMock()
    monkeypatch.setattr(module, "handle_delete_gefyraclient_serviceaccount", delete_sa)

    def make(state="WAITING"):
        data = {
            "metadata": {"name": "client-a", "namespace": "gefyra"},
            "state": state,
            "provider": "stowaway",
            "providerParameter": {"subnet": "10.0.0.0/24"},
        }
        model = module.GefyraClientObject(data)
        model._write_state = Mock()
        client = module.GefyraClient(
            model, module.OperatorConfiguration(), Mock(), initial=state
        )
        client.post_event = AsyncMock()
        client._patch_object = AsyncMock()
        client.cleanup_all_bridges = AsyncMock()
        return client

    return make, provider, delete_sa, module


@pytest.mark.parametrize(
    "state",
    [
        "REQUESTED",
        "CREATING",
        "WAITING",
        "ENABLING",
        "ACTIVE",
        "DISABLING",
        "ERROR",
        "TERMINATING",
    ],
)
async def test_termination_from_every_state_is_repeatable(make_client, state):
    make, provider, delete_sa, _ = make_client
    client = make(state)
    await client.activate_initial_state()
    await client.terminate()
    await client.terminate()
    assert client.terminating.is_active
    assert provider.remove_peer.await_count == 2
    assert delete_sa.await_count == 2
    assert client.cleanup_all_bridges.await_count == 2


@pytest.mark.parametrize("stage", ["peer", "serviceaccount", "bridges"])
async def test_deletion_failure_propagates_and_can_be_retried(make_client, stage):
    from gefyra.handler.clients import client_deleted

    make, provider, delete_sa, module = make_client
    client = make("ENABLING")
    error = module.k8s.client.ApiException(status=0, reason="cleanup failed")
    operation = {
        "peer": provider.remove_peer,
        "serviceaccount": delete_sa,
        "bridges": client.cleanup_all_bridges,
    }[stage]
    operation.side_effect = [error, None]
    # Exercise the real deletion handler: an exception must reach Kopf.
    with patch("gefyra.handler.clients.GefyraClient", return_value=client):
        with pytest.raises(module.k8s.client.ApiException) as raised:
            await client_deleted(client.data, Mock())
        assert raised.value is error
        await client_deleted(client.data, Mock())


async def test_failed_peer_creation_does_not_enable_client(make_client):
    make, provider, _, _ = make_client
    client = make()
    provider.add_peer.side_effect = RuntimeError("provisioning failed")
    with pytest.raises(RuntimeError, match="provisioning failed"):
        await client.enable()
    assert client.waiting.is_active


@pytest.mark.parametrize("stage", ["config", "patch", "state"])
async def test_failed_activation_does_not_report_success(make_client, stage):
    make, provider, _, module = make_client
    client = make("ENABLING")
    error = module.k8s.client.ApiException(status=403, reason="activation failed")
    if stage == "config":
        provider.get_peer_config.side_effect = error
    elif stage == "patch":
        client._patch_object.side_effect = error
    else:
        client.model._write_state.side_effect = error
    with pytest.raises((module.kopf.TemporaryError, module.k8s.client.ApiException)):
        await client.activate()
    assert not any(
        call.kwargs.get("message", "").endswith("is active")
        for call in client.post_event.await_args_list
    )


async def test_active_event_follows_configuration_and_state_persistence(make_client):
    make, _, _, _ = make_client
    client = make("ENABLING")

    async def event(**kwargs):
        if kwargs["message"].endswith("is active"):
            client._patch_object.assert_awaited_once_with(
                {"providerConfig": {"Interface.Address": "10.0.0.2"}}
            )
            assert client.active.is_active
            assert client.model._write_state.call_args.args == ("ACTIVE",)

    client.post_event.side_effect = event
    await client.activate()
    assert any(
        call.kwargs.get("message", "").endswith("is active")
        for call in client.post_event.await_args_list
    )


@pytest.mark.parametrize("status", [0, 403, 500])
async def test_activation_handler_retries_api_failures(make_client, status):
    from gefyra.handler.clients import client_connection_changed

    make, provider, _, module = make_client
    client = make()
    error = module.k8s.client.ApiException(status=status, reason="provisioning failed")
    provider.add_peer.side_effect = error
    with patch("gefyra.handler.clients.GefyraClient", return_value=client):
        with pytest.raises(
            (module.k8s.client.ApiException, module.kopf.TemporaryError)
        ) as raised:
            await client_connection_changed(True, client.data, Mock())
    assert raised.value is error or raised.value.__cause__ is error
    assert client.waiting.is_active


@pytest.mark.parametrize("status", [0, 403, 500])
async def test_disable_failure_keeps_client_recoverable(make_client, status):
    make, provider, _, module = make_client
    client = make("DISABLING")
    provider.peer_exists.return_value = True
    error = module.k8s.client.ApiException(status=status, reason="removal failed")
    provider.remove_peer.side_effect = error
    with pytest.raises((module.k8s.client.ApiException, module.kopf.TemporaryError)):
        await client.wait()
    assert client.disabling.is_active
    client._patch_object.assert_not_awaited()
