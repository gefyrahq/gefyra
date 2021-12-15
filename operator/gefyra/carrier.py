import logging

import kubernetes as k8s

from gefyra.configuration import configuration

logger = logging.getLogger("gefyra.carrier")


def store_pod_original_config(container: k8s.client.V1Container, ireq_object: object) -> None:
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
    obj["carrierOriginalConfig"] = {"image": container.image, "command": container.command, "args": container.args}
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
    port: int,
    ireq_object: object,
) -> bool:
    """
    Install Gefyra Carrier to the target Pod
    :param api_instance: k8s.client.CoreV1Api
    :param pod_name: the name of the Pod to be patched with Carrier
    :param namespace: the namespace of the target Pod runs in
    :param container_name: the container to be exchanged with Carrier
    :param port: the port that Carrier is supposed to be forwarded
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
            store_pod_original_config(container, ireq_object)
            container.image = f"{configuration.CARRIER_IMAGE}:{configuration.CARRIER_IMAGE_TAG}"
            break
    else:
        logger.error(f"Could not found container {container_name} in Pod {pod_name}")
        return False
    logger.info(f"Now patching Pod {pod_name}; container {container_name} with Carrier on port {port}")
    api_instance.patch_namespaced_pod(name=pod_name, namespace=namespace, body=pod)
    return True


def patch_pod_with_original_config(
    api_instance: k8s.client.CoreV1Api, pod_name: str, namespace: str, container_name: str, ireq_object: object
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
        logger.error(f"Could not found container {container_name} in Pod {pod_name}: cannot patch with original state")
        return False
    logger.info(f"Now patching Pod {pod_name}; container {container_name} with original state")
    api_instance.patch_namespaced_pod(name=pod_name, namespace=namespace, body=pod)
    return True
