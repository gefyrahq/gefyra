import logging
import os
import time
from datetime import datetime

import kubernetes as k8s

logger = logging.getLogger(__name__)

k8s.config.load_kube_config()
logger.info("Loaded KUBECONFIG config")
custom_object_api = k8s.client.CustomObjectsApi()
core_api = k8s.client.CoreV1Api()

NAMESPACE = os.getenv("GEFYRA_NAMESPACE", "gefyra")


def create_random_interceptrequest():
    custom_object_api.create_namespaced_custom_object(
        namespace=NAMESPACE,
        body={
            "apiVersion": "gefyra.dev/v1",
            "kind": "InterceptRequest",
            "metadata": {
                "name": "test-interceptrequest-" + datetime.now().strftime("%Y%m%d%H%M%S"),  # noqa
                "namspace": "gefyra",
            },
            "destinationIP": "192.168.126.2",
            "destinationPort": "8000",
            "targetPod": "hello-nginxdemo-7d648bd866-2q7rw",
            "targetNamespace": "default",
            "targetContainer": "hello-nginx",
            "targetContainerPort": "80",
        },
        group="gefyra.dev",
        plural="interceptrequests",
        version="v1",
    )


if __name__ == "__main__":
    tic = time.perf_counter()
    create_random_interceptrequest()
    w = k8s.watch.Watch()

    for event in w.stream(core_api.list_namespaced_event, namespace=NAMESPACE):
        if event["object"].reason in ["Established"]:
            toc = time.perf_counter()
            print(f"Gefyra IREQ ready in {toc - tic:0.4f} seconds")
            break
