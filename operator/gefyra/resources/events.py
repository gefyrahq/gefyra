from datetime import datetime

import kubernetes as k8s


def _get_now() -> str:
    return datetime.utcnow().isoformat(timespec="microseconds") + "Z"


def create_operator_ready_event(namespace: str) -> k8s.client.EventsV1Event:
    now = _get_now()
    return k8s.client.EventsV1Event(
        metadata=k8s.client.V1ObjectMeta(
            name="gefyra-operator-startup", namespace=namespace
        ),
        reason="Gefyra-Ready",
        note="Operator has been started configured successfully",
        event_time=now,
        action="Startup",
        type="Normal",
        reporting_instance="gefyra-operator",
        reporting_controller="gefyra-operator",
        regarding=k8s.client.V1ObjectReference(
            kind="deployment", name="gefyra-operator", namespace=namespace
        ),
    )


def create_operator_webhook_ready_event(namespace: str) -> k8s.client.EventsV1Event:
    now = _get_now()
    return k8s.client.EventsV1Event(
        metadata=k8s.client.V1ObjectMeta(
            name="gefyra-operator-startup", namespace=namespace
        ),
        reason="Gefyra-Webhook-Ready",
        note="Operator Webhook has been started configured successfully",
        event_time=now,
        action="Startup",
        type="Normal",
        reporting_instance="gefyra-operator-webhook",
        reporting_controller="gefyra-operator-webhook",
        regarding=k8s.client.V1ObjectReference(
            kind="deployment", name="gefyra-operator-webhook", namespace=namespace
        ),
    )
