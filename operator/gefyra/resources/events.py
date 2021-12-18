from datetime import datetime

import kubernetes as k8s


def create_interceptrequest_established_event(
    intercept_request_name: str,
    namespace: str,
    pod_name: str,
    container_name: str,
    container_port: int,
) -> k8s.client.EventsV1Event:
    return k8s.client.EventsV1Event(
        reason="Established",
        reporting_controller="gefyra-operator",
        note=f"This InterceptRequest route on Pod {pod_name} container {container_name}:{container_port}"
        f" has been established",
        event_time=datetime.now().isoformat() + "+00:00",
        regarding=k8s.client.V1ObjectReference(
            kind="interceptrequest", name=intercept_request_name, namespace=namespace
        ),
    )


def create_operator_ready_event(namespace: str) -> k8s.client.EventsV1Event:
    return k8s.client.EventsV1Event(
        reason="Startup",
        reporting_controller="gefyra-operator",
        note="Operator has been started configured successfully",
        event_time=datetime.now().isoformat() + "+00:00",
        regarding=k8s.client.V1ObjectReference(
            kind="deployment", name="gefyra-operator", namespace=namespace
        ),
    )
