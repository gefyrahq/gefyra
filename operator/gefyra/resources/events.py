from datetime import datetime

import kubernetes as k8s


def create_interceptrequest_established_event(
    intercept_request_name: str, namespace: str
) -> k8s.client.EventsV1Event:
    return k8s.client.EventsV1Event(
        note="This InterceptRequest route has been established",
        event_time=datetime.now().isoformat(),
        regarding=k8s.client.V1ObjectReference(
            kind="interceptrequest", name=intercept_request_name, namespace=namespace
        ),
    )


def create_operator_ready_event(namespace: str) -> k8s.client.EventsV1Event:
    return k8s.client.EventsV1Event(
        reason="Startup",
        note="Operator has been started configured successfully",
        event_time=datetime.now().isoformat(),
        regarding=k8s.client.V1ObjectReference(
            kind="deployment", name="gefyra-operator", namespace=namespace
        ),
    )
