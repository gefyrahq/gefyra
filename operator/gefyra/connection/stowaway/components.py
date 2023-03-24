import kubernetes as k8s

from gefyra.configuration import OperatorConfiguration
from gefyra.connection.stowaway.resources import (
    create_stowaway_proxyroute_configmap,
    create_stowaway_deployment,
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


def handle_stowaway_deployment(
    logger, configuration: OperatorConfiguration, labels: dict[str, str]
) -> k8s.client.V1Deployment:
    deployment_stowaway = create_stowaway_deployment(labels)

    try:
        app.create_namespaced_deployment(
            body=deployment_stowaway, namespace=configuration.NAMESPACE
        )
        logger.info("Stowaway deployment created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # the Stowaway deployment already exist
            logger.warn(
                "Stowaway deployment already available, now patching it with current configuration"
            )
            app.patch_namespaced_deployment(
                name=deployment_stowaway.metadata.name,
                body=deployment_stowaway,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Stowaway deployment patched")
        else:
            raise e
    return deployment_stowaway


def handle_stowaway_nodeport_service(
    logger,
    configuration: OperatorConfiguration,
    deployment_stowaway: k8s.client.V1Deployment,
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


def handle_stowaway_rsync_service(
    logger,
    configuration: OperatorConfiguration,
    deployment_stowaway: k8s.client.V1Deployment,
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
