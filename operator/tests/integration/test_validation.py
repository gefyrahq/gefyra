from datetime import datetime
import logging
from gefyra.clientstate import GefyraClient
import pytest
from pytest_kubernetes.providers import AClusterManager


def test_a_gefyraclients_validator(operator: AClusterManager):
    import kopf
    from gefyra.handler.configure_webhook import check_validate_provider_parameters

    logger = logging.getLogger()
    operation = "CREATE"
    diff = {}
    body = {"metadata": {"name": "test1"}, "provider": "stowaway"}
    check_validate_provider_parameters(body, diff, logger, operation)

    body = {
        "metadata": {"name": "test1"},
        "provider": "stowaway",
        "sunset": f"{datetime.now().isoformat()}Z",
    }
    check_validate_provider_parameters(body, diff, logger, operation)

    body = {
        "metadata": {"name": "test1"},
        "provider": "stowaway",
        "sunset": "ain't correct",
    }
    with pytest.raises(kopf.AdmissionError):
        check_validate_provider_parameters(body, diff, logger, operation)

    body = {
        "metadata": {"name": "test1"},
        "provider": "stowaway",
        "providerParameter": {"subnet": "192.168.300.0/24"},
    }
    with pytest.raises(kopf.AdmissionError):
        check_validate_provider_parameters(body, diff, logger, operation)

    operation = "UPDATE"
    body = {
        "metadata": {"name": "test1"},
        "provider": "stowaway",
        "providerParameter": {"subnet": "192.168.300.0/24"},
        "state": GefyraClient.waiting.value,
    }
    diff = [("add", ("providerParameter",), None, {"subnet": "192.168.300.0/24"})]
    check_validate_provider_parameters(body, diff, logger, operation)

    operation = "UPDATE"
    body = {
        "metadata": {"name": "test1"},
        "provider": "stowaway",
        "providerParameter": {"subnet": "192.168.300.0/24"},
        "state": GefyraClient.active.value,
    }
    diff = [
        (
            "change",
            ("providerParameter",),
            {"subnet": "192.168.300.1/24"},
            {"subnet": "192.168.300.0/24"},
        )
    ]
    with pytest.raises(kopf.AdmissionError):
        check_validate_provider_parameters(body, diff, logger, operation)

    operation = "UPDATE"
    body = {
        "metadata": {"name": "test1"},
        "provider": "stowaway",
        "providerParameter": {},
        "state": GefyraClient.active.value,
    }
    diff = [("change", ("providerParameter",), {"subnet": "192.168.300.1/24"}, {})]
    check_validate_provider_parameters(body, diff, logger, operation)
