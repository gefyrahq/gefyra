import logging

import kopf


@kopf.on.startup()
def configure(logger, settings: kopf.OperatorSettings, **_):
    settings.peering.standalone = True
    settings.posting.level = logging.WARNING
    settings.posting.enabled = False
    settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
        prefix="gefyra.dev",
        key="last-handled-configuration",
    )
    settings.persistence.finalizer = "operator.gefyra.dev/kopf-finalizer"
    settings.networking.request_timeout = 30
    settings.networking.connect_timeout = 12
    settings.watching.connect_timeout = 10
    settings.watching.client_timeout = 25
    settings.watching.server_timeout = 20
    logger.info(f"Gefyra Operator Kopf configuration: {settings}")
