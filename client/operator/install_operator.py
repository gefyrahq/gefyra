import logging
import os
import time

import kubernetes as k8s

from .resources import (
    create_operator_clusterrole,
    create_operator_clusterrolebinding,
    create_operator_deployment,
    create_operator_serviceaccount,
)
from .utils import decode_secret

logger = logging.getLogger(__name__)

k8s.config.load_kube_config()
logger.info("Loaded KUBECONFIG config")
core_api = k8s.client.CoreV1Api()
rbac_api = k8s.client.RbacAuthorizationV1Api()
app_api = k8s.client.AppsV1Api()
NAMESPACE = os.getenv("GEFYRA_NAMESPACE", "gefyra")


def handle_serviceaccount(serviceaccount):
    try:
        core_api.create_namespaced_service_account(
            body=serviceaccount, namespace=NAMESPACE
        )
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
        app_api.create_namespaced_deployment(
            body=operator_deployment, namespace=NAMESPACE
        )
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


def install_operator():
    tic = time.perf_counter()
    try:
        core_api.create_namespace(
            body=k8s.client.V1Namespace(
                metadata=k8s.client.V1ObjectMeta(name=NAMESPACE)
            )
        )
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # namespace does already exist
            pass
        else:
            raise e

    serviceaccount = create_operator_serviceaccount(NAMESPACE)
    clusterrole = create_operator_clusterrole()
    clusterrolebinding = create_operator_clusterrolebinding(
        serviceaccount, clusterrole, NAMESPACE
    )
    operator_deployment = create_operator_deployment(serviceaccount, NAMESPACE)
    handle_serviceaccount(serviceaccount)
    handle_clusterrole(clusterrole)
    handle_clusterrolebinding(clusterrolebinding)
    handle_deployment(operator_deployment)

    w = k8s.watch.Watch()

    # block (forever) until Gefyra cluster side is ready
    for event in w.stream(core_api.list_namespaced_event, namespace=NAMESPACE):
        if event["object"].reason in ["Pulling", "Pulled"]:
            print(event["object"].message)
        if event["object"].reason == "Gefyra-Ready":
            toc = time.perf_counter()
            print(f"Gefyra ready in {toc - tic:0.4f} seconds")
            break

    cargo_connection_secret = core_api.read_namespaced_secret(
        name="gefyra-cargo-connection", namespace=NAMESPACE
    )
    values = decode_secret(cargo_connection_secret.data)
    print("Cargo connection details")
    print(values)


if __name__ == "__main__":
    install_operator()
