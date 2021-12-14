from datetime import datetime

import kubernetes as k8s


def create_interceptrequest_established_event(
    intercept_request_name: str, namespace: str
) -> k8s.client.EventsV1Event:
    event = k8s.client.EventsV1Event(
        note="This InterceptRequest route has been established",
        event_time=datetime.now().strftime("%Y%m%d%H%M%S"),
        regarding=k8s.client.V1ObjectReference(
            name=intercept_request_name, namespace=namespace
        ),
    )
    return event
