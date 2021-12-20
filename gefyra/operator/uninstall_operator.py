import logging
import os
from time import sleep

import kubernetes as k8s
from resources import (
    create_operator_clusterrole,
    create_operator_clusterrolebinding,
    create_operator_deployment,
    create_operator_serviceaccount,
)

logger = logging.getLogger(__name__)

k8s.config.load_kube_config()
logger.info("Loaded KUBECONFIG config")
core_api = k8s.client.CoreV1Api()
rbac_api = k8s.client.RbacAuthorizationV1Api()
app_api = k8s.client.AppsV1Api()
NAMESPACE = os.getenv("GEFYRA_NAMESPACE", "../../operator/operator")


if __name__ == "__main__":

    serviceaccount = create_operator_serviceaccount(NAMESPACE)
    clusterrole = create_operator_clusterrole()
    clusterrolebinding = create_operator_clusterrolebinding(serviceaccount, clusterrole, NAMESPACE)
    operator_deployment = create_operator_deployment(serviceaccount, NAMESPACE)
    try:
        app_api.delete_namespaced_deployment(name=operator_deployment.metadata.name, namespace=NAMESPACE)
        # pause to let Operator shutdown properly
        sleep(5)
        core_api.delete_namespaced_service_account(name=serviceaccount.metadata.name, namespace=NAMESPACE)
        rbac_api.delete_cluster_role(name=clusterrole.metadata.name)
        rbac_api.delete_cluster_role_binding(name=clusterrolebinding.metadata.name)
    except k8s.client.exceptions.ApiException:
        pass

    try:
        core_api.delete_namespace(name=NAMESPACE)
    except k8s.client.exceptions.ApiException as e:
        raise e
