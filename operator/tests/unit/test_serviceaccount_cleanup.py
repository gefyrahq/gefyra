from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("missing", ["binding", "serviceaccount", "both"])
async def test_cleanup_handles_independently_missing_resources(monkeypatch, missing):
    from gefyra.resources import serviceaccounts as module

    core, rbac = Mock(), Mock()
    monkeypatch.setattr(module, "core_v1_api", core)
    monkeypatch.setattr(module, "rbac_v1_api", rbac)
    if missing in ("binding", "both"):
        rbac.delete_cluster_role_binding.side_effect = module.k8s.client.ApiException(
            status=404
        )
    if missing in ("serviceaccount", "both"):
        core.delete_namespaced_service_account.side_effect = (
            module.k8s.client.ApiException(status=404)
        )

    await module.handle_delete_gefyraclient_serviceaccount(
        Mock(), "gefyra-client-a", "gefyra"
    )

    rbac.delete_cluster_role_binding.assert_called_once_with(
        name="gefyra-rolebinding-gefyra-client-a"
    )
    core.delete_namespaced_service_account.assert_called_once_with(
        name="gefyra-client-a", namespace="gefyra"
    )


@pytest.mark.parametrize("resource", ["binding", "serviceaccount"])
async def test_cleanup_preserves_api_errors(monkeypatch, resource):
    from gefyra.resources import serviceaccounts as module

    core, rbac = Mock(), Mock()
    monkeypatch.setattr(module, "core_v1_api", core)
    monkeypatch.setattr(module, "rbac_v1_api", rbac)
    error = module.k8s.client.ApiException(status=0, reason="transport failed")
    operation = (
        rbac.delete_cluster_role_binding
        if resource == "binding"
        else core.delete_namespaced_service_account
    )
    operation.side_effect = error
    with pytest.raises(module.k8s.client.ApiException) as raised:
        await module.handle_delete_gefyraclient_serviceaccount(
            Mock(), "gefyra-client-a", "gefyra"
        )
    assert raised.value is error
