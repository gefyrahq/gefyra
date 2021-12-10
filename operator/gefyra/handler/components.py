import asyncio

import kopf
import kubernetes as k8s

from gefyra.configuration import OperatorConfiguration
from gefyra.resources.configmaps import create_stowaway_proxyroute_configmap
from gefyra.resources.crds import create_interceptrequest_definition
from gefyra.resources.deployments import create_stowaway_deployment
from gefyra.resources.services import create_stowaway_nodeport_service
from gefyra.stowaway import check_stowaway_ready, get_wireguard_connection_details

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
extension_api = k8s.client.ApiextensionsV1Api()


def handle_crds(logger) -> k8s.client.V1CustomResourceDefinition:
    ireqs = create_interceptrequest_definition()
    try:
        extension_api.create_custom_resource_definition(body=ireqs)
        logger.info("Gefyra CRD InterceptRequest created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # the Stowaway proxy route configmap exist
            logger.warn("Gefyra CRD InterceptRequest already available")
        else:
            raise e
    return ireqs


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
    logger, configuration: OperatorConfiguration
) -> k8s.client.V1Deployment:
    deployment_stowaway = create_stowaway_deployment()

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


@kopf.on.startup()
async def check_gefyra_components(logger, **kwargs) -> None:
    """
    Checks all required components of Gefyra in the current version. This handler installs components if they are
    not already available with the matching configuration.
    """
    from gefyra.configuration import configuration

    logger.info(
        f"Ensuring Gefyra components with the following configuration: {configuration}"
    )

    #
    # handle Gefyra CRDs and Permissions
    #
    handle_crds(logger)

    #
    # handle Stowaway proxy route configmap
    #
    handle_proxyroute_configmap(logger, configuration)

    #
    # handle Stowaway deployment
    #
    deployment_stowaway = handle_stowaway_deployment(logger, configuration)

    #
    # handle Stowaway nodeport service
    #
    handle_stowaway_nodeport_service(logger, configuration, deployment_stowaway)

    #
    # schedule startup tasks, work on them async
    #
    aw_stowaway_ready = asyncio.create_task(check_stowaway_ready(deployment_stowaway))
    asyncio.create_task(get_wireguard_connection_details(aw_stowaway_ready))

    logger.info("Gefyra components installed/patched")
