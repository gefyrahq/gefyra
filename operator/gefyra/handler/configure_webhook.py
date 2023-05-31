import logging

import kopf

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
