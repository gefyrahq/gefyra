import kubernetes as k8s

from gefyra.configuration import OperatorConfiguration
from gefyra.connection.stowaway.resources import (
    create_stowaway_proxyroute_configmap,
    create_stowaway_statefulset,
    create_stowaway_serviceaccount,
    create_stowaway_nodeport_service,
    create_stowaway_rsync_service,
)

core_v1_api = k8s.client.CoreV1Api()
app = k8s.client.AppsV1Api()


def handle_serviceaccount(logger, configuration: OperatorConfiguration):
    serviceaccount = create_stowaway_serviceaccount()
    try:
        core_v1_api.create_namespaced_service_account(
            body=serviceaccount, namespace=configuration.NAMESPACE
        )
        logger.info("Gefyra Stowaway Serviceaccount created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


def check_serviceaccount(logger, configuration: OperatorConfiguration):
    serviceaccount = create_stowaway_serviceaccount()
    try:
        core_v1_api.read_namespaced_service_account(
            serviceaccount.metadata.name, serviceaccount.metadata.namespace
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warn("Gefyra Stowaway Serviceaccount does not exist")
            return False
        else:
            raise e


def handle_proxyroute_configmap(
    logger, configuration: OperatorConfiguration
) -> k8s.client.V1ConfigMap:
    # Todo recover from restart; read in all <InterceptRequests>
    configmap_proxyroute = create_stowaway_proxyroute_configmap()

    try:
        core_v1_api.create_namespaced_config_map(
            body=configmap_proxyroute, namespace=configuration.NAMESPACE
        )
        logger.info("Stowaway proxy route configmap created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # the Stowaway proxy route configmap exist
            logger.warn(
                "Stowaway proxy route configmap already available, now patching it with current configuration"
            )
            core_v1_api.replace_namespaced_config_map(
                name=configmap_proxyroute.metadata.name,
                body=configmap_proxyroute,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Stowaway proxy route configmap patched")
        else:
            raise e
    return configmap_proxyroute


def check_proxyroute_configmap(
    logger, configuration: OperatorConfiguration
) -> k8s.client.V1ConfigMap:
    configmap_proxyroute = create_stowaway_proxyroute_configmap()
    try:
        core_v1_api.read_namespaced_config_map(
            configmap_proxyroute.metadata.name, configmap_proxyroute.metadata.namespace
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warn("Stowaway proxy route configmap does not exist")
            return False
        else:
            raise e


def handle_stowaway_statefulset(
    logger, configuration: OperatorConfiguration, labels: dict[str, str]
) -> k8s.client.V1StatefulSet:
    deployment_stowaway = create_stowaway_statefulset(labels)

    try:
        app.create_namespaced_stateful_set(
            body=deployment_stowaway, namespace=configuration.NAMESPACE
        )
        logger.info("Stowaway deployment created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # the Stowaway deployment already exist
            logger.warn(
                "Stowaway deployment already available, now patching it with current configuration"
            )
            app.patch_namespaced_stateful_set(
                name=deployment_stowaway.metadata.name,
                body=deployment_stowaway,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Stowaway deployment patched")
        else:
            raise e
    return deployment_stowaway


def check_stowaway_statefulset(
    logger, configuration: OperatorConfiguration, labels: dict[str, str]
) -> bool:
    deployment_stowaway = create_stowaway_statefulset(labels)
    try:
        app.read_namespaced_stateful_set(
            deployment_stowaway.metadata.name, deployment_stowaway.metadata.namespace
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warn("Stowaway deployment does not exist")
            return False
        else:
            raise e


def handle_stowaway_nodeport_service(
    logger,
    configuration: OperatorConfiguration,
    deployment_stowaway: k8s.client.V1StatefulSet,
):
    nodeport_service_stowaway = create_stowaway_nodeport_service(deployment_stowaway)
    try:
        core_v1_api.create_namespaced_service(
            body=nodeport_service_stowaway, namespace=configuration.NAMESPACE
        )
        logger.info("Stowaway nodeport service created")
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            # the Stowaway service already exist
            # status == 422 is nodeport already allocated
            logger.warn(
                "Stowaway nodeport service already available, now patching it with current configuration"
            )
            core_v1_api.patch_namespaced_service(
                name=nodeport_service_stowaway.metadata.name,
                body=nodeport_service_stowaway,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Stowaway nodeport service patched")
        else:
            raise e


def check_stowaway_nodeport_service(
    logger,
    configuration: OperatorConfiguration,
    deployment_stowaway: k8s.client.V1StatefulSet,
):
    nodeport_service_stowaway = create_stowaway_nodeport_service(deployment_stowaway)
    try:
        core_v1_api.read_namespaced_service(
            nodeport_service_stowaway.metadata.name,
            nodeport_service_stowaway.metadata.namespace,
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warn("Stowaway nodeport service does not exist")
            return False
        else:
            raise e


def handle_stowaway_rsync_service(
    logger,
    configuration: OperatorConfiguration,
    deployment_stowaway: k8s.client.V1StatefulSet,
):
    rsync_service_stowaway = create_stowaway_rsync_service(deployment_stowaway)
    try:
        core_v1_api.create_namespaced_service(
            body=rsync_service_stowaway, namespace=configuration.NAMESPACE
        )
        logger.info("Stowaway rsync service created")
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            # the Stowaway service already exist
            # status == 422 is rsync already allocated
            logger.warn(
                "Stowaway rsync service already available, now patching it with current configuration"
            )
            core_v1_api.patch_namespaced_service(
                name=rsync_service_stowaway.metadata.name,
                body=rsync_service_stowaway,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Stowaway rsync service patched")
        else:
            raise e


def check_stowaway_rsync_service(
    logger,
    configuration: OperatorConfiguration,
    deployment_stowaway: k8s.client.V1StatefulSet,
):
    rsync_service_stowaway = create_stowaway_rsync_service(deployment_stowaway)
    try:
        core_v1_api.read_namespaced_service(
            rsync_service_stowaway.metadata.name,
            rsync_service_stowaway.metadata.namespace,
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warn("Stowaway rsync service does not exist")
            return False
        else:
            raise e
