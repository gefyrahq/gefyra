import logging
import os
from datetime import datetime

import kubernetes as k8s

logger = logging.getLogger(__name__)

# if the operator is executed locally load the current KUBECONFIG
k8s.config.load_kube_config()
logger.info("Loaded KUBECONFIG config")
custom_object_api = k8s.client.CustomObjectsApi()
namespace = os.getenv("GEFYRA_NAMESPACE", "default")


def create_random_interceptrequest():
    custom_object_api.create_namespaced_custom_object(
        namespace=namespace,
        body={
            "apiVersion": "gefyra.dev/v1",
            "kind": "InterceptRequest",
            "metadata": {
                "name": "test-interceptrequest-" + datetime.now().strftime("%Y%m%d%H%M%S"),
            },
            "destinationIP": "my-nginx-headless",
            "destinationPort": "80",
            "targetPod": "nginx-deployment-66b6c48dd5-x7vwr",
            "targetNamespace": "default",
            "targetContainer": "nginx",
            "targetContainerPort": "80",
        },
        group="gefyra.dev",
        plural="interceptrequests",
        version="v1",
    )


if __name__ == "__main__":
    create_random_interceptrequest()
