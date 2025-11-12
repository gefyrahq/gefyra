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


def test_b_gefyrabridgemount_validator(operator: AClusterManager):
    import kopf
    from gefyra.handler.configure_webhook import check_validate_bridgemount_parameters

    logger = logging.getLogger()
    operation = "CREATE"
    diff = {}
    base_body = {"metadata": {"name": "test1"}, "provider": "carrier2mount"}
    with pytest.raises(kopf.AdmissionError):
        check_validate_bridgemount_parameters(base_body, diff, logger, operation)

    body = {**base_body, "target": "abc"}
    with pytest.raises(kopf.AdmissionError):
        check_validate_bridgemount_parameters(body, diff, logger, operation)

    body = {
        **base_body,
        "target": "abc",
        "targetNamespace": "abc",
        "targetContainer": "abc",
    }
    check_validate_bridgemount_parameters(body, diff, logger, operation)

    operation = "UPDATE"
    check_validate_bridgemount_parameters(body, diff, logger, operation)

    operation = "UPDATE"
    diff = [("change", ("target",), "old", "new")]
    with pytest.raises(kopf.AdmissionError):
        check_validate_bridgemount_parameters(body, diff, logger, operation)

    operator.apply("tests/fixtures/nginx.yaml")
    operator.apply("tests/fixtures/bridge_mount.yaml")

    operation = "CREATE"
    body = {
        "metadata": {"name": "test1"},
        "provider": "carrier2mount",
        "target": "nginx-deployment",
        "targetNamespace": "default",
        "targetContainer": "nginx",
    }
    with pytest.raises(kopf.AdmissionError):
        check_validate_bridgemount_parameters(body, diff, logger, operation)


def test_c_gefyrabridge_validator(operator: AClusterManager):
    import kopf
    from gefyra.handler.configure_webhook import check_validate_bridge_parameters

    logger = logging.getLogger()
    operation = "CREATE"
    diff = {}
    base_body = {"metadata": {"name": "test1"}, "provider": "carrier2"}
    with pytest.raises(kopf.AdmissionError):
        check_validate_bridge_parameters(base_body, diff, logger, operation)

    operation = "CREATE"
    diff = {}
    body = {**base_body, "target": "bridgemount-b"}
    with pytest.raises(kopf.AdmissionError):
        # missing labels
        check_validate_bridge_parameters(body, diff, logger, operation)

    operator.apply("tests/fixtures/nginx.yaml")
    operator.apply("tests/fixtures/bridge_mount.yaml")

    operation = "CREATE"
    diff = {}
    body = {**base_body, "target": "bridgemount-b"}
    body["metadata"]["labels"] = {
        "gefyra.dev/bridge-mount": "bridgemount-b",
        "gefyra.dev/client": "client-a",
    }
    with pytest.raises(kopf.AdmissionError):
        # bridge mount does not exist
        check_validate_bridge_parameters(body, diff, logger, operation)

    operation = "CREATE"
    diff = {}
    body = {**base_body, "target": "bridgemount-a"}
    body["metadata"]["labels"] = {
        "gefyra.dev/bridge-mount": "bridgemount-a",
        "gefyra.dev/client": "client-a",
    }

    with pytest.raises(kopf.AdmissionError):
        # is not in ACTIVE state
        check_validate_bridge_parameters(body, diff, logger, operation)

    operator.wait(
        "gefyrabridgemounts.gefyra.dev/bridgemount-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=60,
    )

    operation = "CREATE"
    diff = {}
    body = {**base_body, "target": "bridgemount-a"}
    body["metadata"]["labels"] = {
        "gefyra.dev/bridge-mount": "bridgemount-a",
        "gefyra.dev/client": "client-a",
    }

    check_validate_bridge_parameters(body, diff, logger, operation)

    # TODO check operation = UPDATE
    # TODO check dupuplicate bridge
