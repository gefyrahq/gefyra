import logging
from datetime import datetime

import kopf

from gefyra.clientstate import GefyraClient

from gefyra.configuration import configuration
from gefyra.connection.factory import (
    ConnectionProviderType,
    connection_provider_factory,
)


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.peering.standalone = True
    settings.posting.level = logging.WARNING
    settings.posting.enabled = False
    settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
        prefix="gefyra.dev",
        key="last-handled-configuration",
    )
    settings.persistence.finalizer = "operator.gefyra.dev/kopf-finalizer"
    settings.admission.server = kopf.WebhookServer(
        port=9443,
        certfile="client-cert.pem",
        pkeyfile="client-key.pem",
        host="gefyra-admission.gefyra.svc",
    )


@kopf.on.validate("gefyraclients.gefyra.dev", id="client-parameters")  # type: ignore
def check_validate_provider_parameters(body, diff, logger, operation, **_):
    if body.get("check", False):
        return True
    name = body["metadata"]["name"]
    logger.info(f"Validating provider parameters for GefyraClient {name}")
    provider_parameter = body["provider"]
    provider = connection_provider_factory.get(
        ConnectionProviderType(provider_parameter),
        configuration,
        logger,
    )
    hints = {}
    if operation == "UPDATE":
        changeset = {field[0]: new for op, field, old, new in diff}
        if "providerParameter" in changeset:
            hints["added"] = "providerParameter"
        if (
            "providerParameter" in changeset
            and bool(changeset["providerParameter"]) is True
            and body["state"] != GefyraClient.waiting.value
        ):
            raise kopf.AdmissionError(
                "Cannot set 'providerParameter' when "
                f"state is not {GefyraClient.waiting.value}"
            )
    if operation == "CREATE":
        if bool(body.get("providerParameter")):
            raise kopf.AdmissionError(
                "Cannot set 'providerParameter' when creating a Gefyra client"
            )
    if sunset := body.get("sunset"):
        try:
            datetime.fromisoformat(sunset.strip("Z"))
        except ValueError as e:
            raise kopf.AdmissionError(f"Cannot parse 'sunset': {e}")
    provider.validate(body, hints)
    return True
