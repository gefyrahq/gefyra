import logging
import os

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
NAMESPACE = os.getenv("GEFYRA_NAMESPACE", "gefyra")


def handle_serviceaccount(serviceaccount):
    try:
        core_api.create_namespaced_service_account(body=serviceaccount, namespace=NAMESPACE)
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


def handle_clusterrole(clusterrole):
    try:
        rbac_api.create_cluster_role(body=clusterrole)
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


def handle_clusterrolebinding(clusterrolebinding):
    try:
        rbac_api.create_cluster_role_binding(body=clusterrolebinding)
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


def handle_deployment(operator_deployment):
    try:
        app_api.create_namespaced_deployment(body=operator_deployment, namespace=NAMESPACE)
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


if __name__ == "__main__":
    try:
        core_api.create_namespace(body=k8s.client.V1Namespace(metadata=k8s.client.V1ObjectMeta(name=NAMESPACE)))
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # namespace does already exist
            pass
        else:
            raise e

    serviceaccount = create_operator_serviceaccount(NAMESPACE)
    clusterrole = create_operator_clusterrole()
    clusterrolebinding = create_operator_clusterrolebinding(serviceaccount, clusterrole, NAMESPACE)
    operator_deployment = create_operator_deployment(serviceaccount, NAMESPACE)
    handle_serviceaccount(serviceaccount)
    handle_clusterrole(clusterrole)
    handle_clusterrolebinding(clusterrolebinding)
    handle_deployment(operator_deployment)
