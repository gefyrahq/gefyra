import logging
from asyncio import sleep
from typing import Awaitable, List

import kubernetes as k8s

from gefyra.configuration import configuration
from gefyra.utils import exec_command_pod

logger = logging.getLogger("gefyra.carrier")

CARRIER_CONFIGURE_COMMAND_BASE = ["/bin/busybox", "sh", "setroute.sh"]
CARRIER_RSYNC_COMMAND_BASE = ["/bin/busybox", "sh", "syncdirs.sh"]


def store_pod_original_config(
    container: k8s.client.V1Container, ireq_object: object
) -> None:
    """
    Store the original configuration of that Container in order to restore it once the intercept request is ended
    :param container: V1Container of the Pod in question
    :param ireq_object: the InterceptRequest object
    :return: None
    """
    custom_object_api = k8s.client.CustomObjectsApi()
    # get the relevant data
    obj = custom_object_api.get_namespaced_custom_object(
        name=ireq_object.metadata.name,
        namespace=ireq_object.metadata.namespace,
        group="gefyra.dev",
        plural="interceptrequests",
        version="v1",
    )
    obj["carrierOriginalConfig"] = {
        "image": container.image,
        "command": container.command,
        "args": container.args,
    }
    custom_object_api.patch_namespaced_custom_object(
        name=ireq_object.metadata.name,
        namespace=ireq_object.metadata.namespace,
        body=obj,
        group="gefyra.dev",
        plural="interceptrequests",
        version="v1",
    )


def patch_pod_with_carrier(
    api_instance: k8s.client.CoreV1Api,
    pod_name: str,
    namespace: str,
    container_name: str,
    ports: List[int],
    ireq_object: object,
) -> bool:
    """
    Install Gefyra Carrier to the target Pod
    :param api_instance: k8s.client.CoreV1Api
    :param pod_name: the name of the Pod to be patched with Carrier
    :param namespace: the namespace of the target Pod runs in
    :param container_name: the container to be exchanged with Carrier
    :param ports: the ports that Carrier is supposed to be forwarded
    :param ireq_object: the InterceptRequest object for this process
    :return: True if the patch was successful else False
    """
    try:
        pod = api_instance.read_namespaced_pod(name=pod_name, namespace=namespace)
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(f"The Pod {pod_name} does not exist")
            return False

    for container in pod.spec.containers:
        if container.name == container_name:
            if (
                container.image
                == f"{configuration.CARRIER_IMAGE}:{configuration.CARRIER_IMAGE_TAG}"
            ):
                # this pod/container is already running Carrier
                logger.info(
                    f"The container {container_name} in Pod {pod_name} is already running Carrier"
                )
                return True
            store_pod_original_config(container, ireq_object)
            container.image = (
                f"{configuration.CARRIER_IMAGE}:{configuration.CARRIER_IMAGE_TAG}"
            )
            break
    else:
        logger.error(f"Could not found container {container_name} in Pod {pod_name}")
        return False
    logger.info(
        f"Now patching Pod {pod_name}; container {container_name} with Carrier on ports {ports}"
    )
    api_instance.patch_namespaced_pod(name=pod_name, namespace=namespace, body=pod)
    return True


def patch_pod_with_original_config(
    api_instance: k8s.client.CoreV1Api,
    pod_name: str,
    namespace: str,
    container_name: str,
    ireq_object: object,
) -> bool:
    """
    Install Gefyra Carrier to the target Pod
    :param api_instance: k8s.client.CoreV1Api
    :param pod_name: the name of the Pod to be patched with Carrier
    :param namespace: the namespace of the target Pod runs in
    :param container_name: the container to be exchanged with Carrier
    :param ireq_object: the InterceptRequest object for this process
    :return: True if the patch was successful else False
    """
    try:
        pod = api_instance.read_namespaced_pod(name=pod_name, namespace=namespace)
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(f"The Pod {pod_name} does not exist")
            return False

    for container in pod.spec.containers:
        if container.name == container_name:
            for k, v in ireq_object.get("carrierOriginalConfig").items():
                setattr(container, k, v)
            break
    else:
        logger.error(
            f"Could not found container {container_name} in Pod {pod_name}: cannot patch with original state"
        )
        return False
    logger.info(
        f"Now patching Pod {pod_name}; container {container_name} with original state"
    )
    api_instance.patch_namespaced_pod(name=pod_name, namespace=namespace, body=pod)
    return True


async def check_carrier_ready(
    api_instance: k8s.client.CoreV1Api, pod_name: str, namespace: str
) -> bool:
    try:
        pod = api_instance.read_namespaced_pod(name=pod_name, namespace=namespace)
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(f"The Carrier Pod {pod_name} does not exist")
    i = 0
    try:
        while i <= configuration.CARRIER_STARTUP_TIMEOUT:
            _ready = False
            # iterate all container statuses
            for container_status in pod.status.container_statuses:
                # if one container is carrier...
                if container_status.image_id.startswith(configuration.CARRIER_IMAGE):
                    _ready = True
                    break
            if _ready:
                break
            else:
                logger.info(f"Waiting for Carrier to become read in Pod {pod_name}")
                await sleep(1)
                i += 1
                pod = api_instance.read_namespaced_pod(
                    name=pod_name, namespace=namespace
                )
    except Exception as e:
        logger.error(e)
        return False
    if i >= configuration.CARRIER_STARTUP_TIMEOUT:
        logger.error(f"Carrier in Pod {pod_name} did not become ready")
        return False
    return True


async def configure_carrier(
    aw_carrier_ready: Awaitable,
    api_instance: k8s.client.CoreV1Api,
    pod_name: str,
    namespace: str,
    container_name: str,
    container_port: int,
    stowaway_service_name: str,
    stowaway_service_port: int,
    interceptrequest_name: str,
    sync_down_directories: List[str],
):
    carrier_ready = await aw_carrier_ready
    if not carrier_ready:
        logger.error(
            f"Not able to configure Carrier in Pod {pod_name}. See error above."
        )
        return
    logger.info(f"Carrier ready in Pod {pod_name} to get configured")
    try:
        command = CARRIER_CONFIGURE_COMMAND_BASE + [
            f"{container_port}",
            f"{stowaway_service_name}.{configuration.NAMESPACE}.svc.cluster.local:{stowaway_service_port}",
        ]
        await sleep(5)
        exec_command_pod(api_instance, pod_name, namespace, container_name, command)
        if sync_down_directories:
            logger.info(f"Setting directories in Carrier {pod_name} to be down synced")
            rsync_cmd = (
                CARRIER_RSYNC_COMMAND_BASE
                + [f"{pod_name}/{container_name}"]
                + sync_down_directories
            )

            exec_command_pod(
                api_instance, pod_name, namespace, container_name, rsync_cmd
            )
    except Exception as e:
        logger.error(e)
        return
    logger.info(f"Carrier configured in {pod_name}")
