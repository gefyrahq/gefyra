import logging
import time

from kubernetes.client import (
    V1ServiceAccount,
    V1ClusterRole,
    ApiException,
    V1ClusterRoleBinding,
    V1Deployment,
    V1Namespace,
    V1ObjectMeta,
)
from kubernetes.watch import Watch

from gefyra.configuration import ClientConfiguration

from .resources import (
    create_operator_clusterrole,
    create_operator_clusterrolebinding,
    create_operator_deployment,
    create_operator_serviceaccount,
)
from .utils import decode_secret

logger = logging.getLogger(__name__)


def handle_serviceaccount(
    config: ClientConfiguration, serviceaccount: V1ServiceAccount
):
    try:
        config.K8S_CORE_API.create_namespaced_service_account(
            body=serviceaccount, namespace=config.NAMESPACE
        )
    except ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


def handle_clusterrole(config: ClientConfiguration, clusterrole: V1ClusterRole):
    try:
        config.K8S_RBAC_API.create_cluster_role(body=clusterrole)
    except ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


def handle_clusterrolebinding(
    config: ClientConfiguration, clusterrolebinding: V1ClusterRoleBinding
):
    try:
        config.K8S_RBAC_API.create_cluster_role_binding(body=clusterrolebinding)
    except ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


def handle_deployment(
    config: ClientConfiguration, operator_deployment: V1Deployment
) -> bool:
    try:
        config.K8S_APP_API.create_namespaced_deployment(
            body=operator_deployment, namespace=config.NAMESPACE
        )
        return True
    except ApiException as e:
        if e.status == 409:
            return False
        else:
            raise e


def install_operator(config: ClientConfiguration, gefyra_network_subnet: str) -> dict:
    """
    Installs Gefyra Operator to the configured cluster, waits for the installation to complete and returns the
    connection secrets for Cargo
    :param config: a ClientConfiguration install
    :return: Cargo connection details
    """
    tic = time.perf_counter()
    try:
        config.K8S_CORE_API.create_namespace(
            body=V1Namespace(metadata=V1ObjectMeta(name=config.NAMESPACE))
        )
    except ApiException as e:
        if e.status == 409:
            # namespace does already exist
            pass
        else:
            raise e

    serviceaccount = create_operator_serviceaccount(config.NAMESPACE)
    clusterrole = create_operator_clusterrole()
    clusterrolebinding = create_operator_clusterrolebinding(
        serviceaccount, clusterrole, config.NAMESPACE
    )
    operator_deployment = create_operator_deployment(
        serviceaccount, config.NAMESPACE, f"{gefyra_network_subnet}"
    )
    handle_serviceaccount(config, serviceaccount)
    handle_clusterrole(config, clusterrole)
    handle_clusterrolebinding(config, clusterrolebinding)
    created = handle_deployment(config, operator_deployment)

    if created:
        w = Watch()

        # block (forever) until Gefyra cluster side is ready
        for event in w.stream(
            config.K8S_CORE_API.list_namespaced_event, namespace=config.NAMESPACE
        ):
            if event["object"].reason in ["Pulling", "Pulled"]:
                logger.info(event["object"].message)
            if event["object"].reason == "Gefyra-Ready":
                toc = time.perf_counter()
                logger.info(f"Operator became ready in {toc - tic:0.4f} seconds")
                break
    else:
        logger.info("Gefyra Operator already exists")

    cargo_connection_secret = config.K8S_CORE_API.read_namespaced_secret(
        name="gefyra-cargo-connection", namespace=config.NAMESPACE
    )
    values = decode_secret(cargo_connection_secret.data)
    logger.debug("Cargo connection details")
    logger.debug(values)
    return values


def uninstall_operator(config: ClientConfiguration):
    serviceaccount = create_operator_serviceaccount(config.NAMESPACE)
    clusterrole = create_operator_clusterrole()
    clusterrolebinding = create_operator_clusterrolebinding(
        serviceaccount, clusterrole, config.NAMESPACE
    )
    operator_deployment = create_operator_deployment(
        serviceaccount, config.NAMESPACE, ""
    )
    try:
        config.K8S_APP_API.delete_namespaced_deployment(
            name=operator_deployment.metadata.name, namespace=config.NAMESPACE
        )
        # pause to let Operator shutdown properly
        time.sleep(5)
        config.K8S_CORE_API.delete_namespaced_service_account(
            name=serviceaccount.metadata.name, namespace=config.NAMESPACE
        )
        config.K8S_RBAC_API.delete_cluster_role(name=clusterrole.metadata.name)
        config.K8S_RBAC_API.delete_cluster_role_binding(
            name=clusterrolebinding.metadata.name
        )
    except ApiException:
        pass

    try:
        config.K8S_CORE_API.delete_namespace(name=config.NAMESPACE)
    except ApiException as e:
        if e.status == 404:
            pass
        else:
            raise e
