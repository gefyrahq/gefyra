import kopf
import kubernetes as k8s

from gefyra.configuration import configuration
from gefyra.resources.configmaps import add_route, remove_route
from gefyra.resources.services import create_stowaway_proxy_service
from gefyra.utils import exec_command_pod, get_deployment_of_pod, notify_stowaway_pod

core_v1_api = k8s.client.CoreV1Api()
app_v1_api = k8s.client.AppsV1Api()
events_v1_api = k8s.client.EventsV1Api()

PROXY_RELOAD_COMMAND = ["/bin/bash", "generate-proxyroutes.sh", "/stowaway/proxyroutes/"]


def handle_stowaway_proxy_service(logger, deployment_stowaway: k8s.client.V1Deployment, port: int):
    proxy_service_stowaway = create_stowaway_proxy_service(deployment_stowaway, port)
    try:
        core_v1_api.create_namespaced_service(body=proxy_service_stowaway, namespace=configuration.NAMESPACE)
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


@kopf.on.create("interceptrequest")
async def interceptrequest_created(body, logger, **kwargs):
    from gefyra.stowaway import STOWAWAY_POD

    name = body.metadata.name
    # is this connection already established
    # established = body.get("established")
    # destination host and port
    destination_ip = body.get("destinationIP")
    destination_port = body.get("destinationPort")
    # the target Pod information
    # target_pod = body.get("targetPod")
    # target_workload = body.get("targetWorkload")
    # target_container = body.get("targetContainer")
    # target_container_port = body.get("targetContainerPort")

    configmap_update, port = add_route(destination_ip, destination_port)
    core_v1_api.replace_namespaced_config_map(
        name=configmap_update.metadata.name,
        body=configmap_update,
        namespace=configuration.NAMESPACE,
    )
    # this logger instance logs directly onto the InterceptRequest object instance as an event
    logger.info("Added intercept route: Stowaway proxy route configmap patched")

    if STOWAWAY_POD:
        notify_stowaway_pod(core_v1_api, STOWAWAY_POD, configuration)
        exec_command_pod(core_v1_api, STOWAWAY_POD, configuration.NAMESPACE, PROXY_RELOAD_COMMAND)
        stowaway_deployment = get_deployment_of_pod(app_v1_api, STOWAWAY_POD, configuration.NAMESPACE)
        handle_stowaway_proxy_service(logger, stowaway_deployment, port)
        logger.info(f"Created route for InterceptRequest {name}")
    else:
        logger.error("Could not modify Stowaway with new intercept request")

    #
    # handle target Pod/workload
    #
    logger.info(f"Traffic interception for {name} has been established")


@kopf.on.delete("interceptrequest")
async def interceptrequest_deleted(body, logger, **kwargs):
    from gefyra.stowaway import STOWAWAY_POD

    name = body.metadata.name
    # is this connection already established
    # established = body.get("established")
    # destination host and port
    destination_ip = body.get("destinationIP")
    destination_port = body.get("destinationPort")
    # the target Pod information
    # target_pod = body.get("targetPod")
    # target_workload = body.get("targetWorkload")
    # target_container = body.get("targetContainer")
    # target_container_port = body.get("targetContainerPort")

    configmap_update, port = remove_route(destination_ip, destination_port)
    core_v1_api.replace_namespaced_config_map(
        name=configmap_update.metadata.name,
        body=configmap_update,
        namespace=configuration.NAMESPACE,
    )
    logger.info("Remove intercept route: Stowaway proxy route configmap patched")

    #
    # handle target Pod/workload
    #

    if STOWAWAY_POD:
        if port is None:
            logger.warning(f"Could not delete service for intercept route {name}: no proxy port found")
        else:
            core_v1_api.delete_namespaced_service(
                name=f"gefyra-stowaway-proxy-{port}", namespace=configuration.NAMESPACE
            )
        notify_stowaway_pod(core_v1_api, STOWAWAY_POD, configuration)
        exec_command_pod(core_v1_api, STOWAWAY_POD, configuration.NAMESPACE, PROXY_RELOAD_COMMAND)
        logger.info(f"Removed route for InterceptRequest {name}")
    else:
        logger.error("Could not notify Stowaway about the new intercept request")
