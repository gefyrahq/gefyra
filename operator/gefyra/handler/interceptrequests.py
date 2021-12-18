import asyncio

import kopf
import kubernetes as k8s

from gefyra.carrier import (
    check_carrier_ready,
    configure_carrier,
    patch_pod_with_carrier,
    patch_pod_with_original_config,
)
from gefyra.configuration import configuration
from gefyra.resources.configmaps import add_route, remove_route
from gefyra.resources.services import create_stowaway_proxy_service
from gefyra.utils import exec_command_pod, get_deployment_of_pod, notify_stowaway_pod

core_v1_api = k8s.client.CoreV1Api()
app_v1_api = k8s.client.AppsV1Api()
events_v1_api = k8s.client.EventsV1Api()

PROXY_RELOAD_COMMAND = [
    "/bin/bash",
    "generate-proxyroutes.sh",
    "/stowaway/proxyroutes/",
]


def handle_stowaway_proxy_service(
    logger, deployment_stowaway: k8s.client.V1Deployment, port: int
) -> k8s.client.V1Service:
    proxy_service_stowaway = create_stowaway_proxy_service(deployment_stowaway, port)
    try:
        core_v1_api.create_namespaced_service(
            body=proxy_service_stowaway, namespace=configuration.NAMESPACE
        )
        logger.info(f"Stowaway proxy service for port {port} created")
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            # the Stowaway service already exist
            # status == 422 is nodeport already allocated
            logger.warn(
                f"Stowaway proxy service for port {port} already available, now patching it with current configuration"
            )
            core_v1_api.patch_namespaced_service(
                name=proxy_service_stowaway.metadata.name,
                body=proxy_service_stowaway,
                namespace=configuration.NAMESPACE,
            )
            logger.info(f"Stowaway proxy service for port {port} patched")
        else:
            raise e
    return proxy_service_stowaway


@kopf.on.create("interceptrequest")
async def interceptrequest_created(body, logger, **kwargs):
    from gefyra.stowaway import STOWAWAY_POD

    # is this connection already established
    # established = body.get("established")
    # destination host and port
    destination_ip = body.get("destinationIP")
    destination_port = body.get("destinationPort")
    # the target Pod information
    target_pod = body.get("targetPod")
    target_namespace = body.get("targetNamespace")
    target_container = body.get("targetContainer")
    target_container_port = body.get("targetContainerPort")

    #
    # handle target Pod
    #
    success = patch_pod_with_carrier(
        core_v1_api,
        pod_name=target_pod,
        namespace=target_namespace,
        container_name=target_container,
        port=int(target_container_port),
        ireq_object=body,
    )
    if not success:
        logger.error(
            "Could not create intercept route because target pod could to be patched with Carrier. "
            "See errors above."
        )
        # instantly remove this InterceptRequest since it's not unsatisfiable
        k8s.client.CustomObjectsApi().delete_namespaced_custom_object(
            name=body.metadata.name,
            namespace=body.metadata.namespace,
            group="gefyra.dev",
            plural="interceptrequests",
            version="v1",
        )
        logger.error(f"Deleted InterceptRequest {body.metadata.name}")
        return

    configmap_update, port = add_route(destination_ip, destination_port)
    core_v1_api.replace_namespaced_config_map(
        name=configmap_update.metadata.name,
        body=configmap_update,
        namespace=configuration.NAMESPACE,
    )
    # this logger instance logs directly onto the InterceptRequest object instance as an event
    logger.info(
        f"Added intercept route: Stowaway proxy route configmap patched with port {port}"
    )

    if STOWAWAY_POD:
        notify_stowaway_pod(core_v1_api, STOWAWAY_POD, configuration)
        exec_command_pod(
            core_v1_api,
            STOWAWAY_POD,
            configuration.NAMESPACE,
            "stowaway",
            PROXY_RELOAD_COMMAND,
        )
        stowaway_deployment = get_deployment_of_pod(
            app_v1_api, STOWAWAY_POD, configuration.NAMESPACE
        )
        proxy_service = handle_stowaway_proxy_service(logger, stowaway_deployment, port)
        logger.info(f"Created route for InterceptRequest {body.metadata.name}")
    else:
        logger.error(
            "Could not modify Stowaway with new intercept request. Removing this InterceptRequest."
        )
        # instantly remove this InterceptRequest since it's not unsatisfiable
        k8s.client.CustomObjectsApi().delete_namespaced_custom_object(
            name=body.metadata.name,
            namespace=body.metadata.namespace,
            group="gefyra.dev",
            plural="interceptrequests",
            version="v1",
        )
        return
    logger.info(f"Traffic interception for {body.metadata.name} has been established")

    #
    # configure Carrier
    #
    aw_carrier_ready = asyncio.create_task(
        check_carrier_ready(core_v1_api, target_pod, target_namespace)
    )
    asyncio.create_task(
        configure_carrier(
            aw_carrier_ready,
            core_v1_api,
            target_pod,
            target_namespace,
            target_container,
            int(target_container_port),
            proxy_service.metadata.name,
            port,
            body.metadata.name,
        )
    )


@kopf.on.delete("interceptrequest")
async def interceptrequest_deleted(body, logger, **kwargs):
    from gefyra.stowaway import STOWAWAY_POD

    name = body.metadata.name
    # is this connection already established
    # destination host and port
    destination_ip = body.get("destinationIP")
    destination_port = body.get("destinationPort")
    # the target Pod information
    target_pod = body.get("targetPod")
    target_namespace = body.get("targetNamespace")
    target_container = body.get("targetContainer")

    configmap_update, port = remove_route(destination_ip, destination_port)
    core_v1_api.replace_namespaced_config_map(
        name=configmap_update.metadata.name,
        body=configmap_update,
        namespace=configuration.NAMESPACE,
    )
    logger.info("Remove intercept route: Stowaway proxy route configmap patched")

    if STOWAWAY_POD:
        if port is None:
            logger.warning(
                f"Could not delete service for intercept route {name}: no proxy port found"
            )
        else:
            core_v1_api.delete_namespaced_service(
                name=f"gefyra-stowaway-proxy-{port}", namespace=configuration.NAMESPACE
            )
        notify_stowaway_pod(core_v1_api, STOWAWAY_POD, configuration)
        exec_command_pod(
            core_v1_api,
            STOWAWAY_POD,
            configuration.NAMESPACE,
            "stowaway",
            PROXY_RELOAD_COMMAND,
        )
        logger.info(f"Removed route for InterceptRequest {name}")
    else:
        logger.error("Could not notify Stowaway about the new intercept request")

    #
    # handle target Pod
    #
    success = patch_pod_with_original_config(
        core_v1_api,
        pod_name=target_pod,
        namespace=target_namespace,
        container_name=target_container,
        ireq_object=body,
    )
    if not success:
        logger.error(
            "Could not restore Pod with original container configuration. See errors above."
        )
