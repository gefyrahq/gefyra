import json
import logging
import multiprocessing
import subprocess
from time import sleep

import docker
from docker.models.containers import Container
import kubernetes as k8s

from gefyra.configuration import ClientConfiguration

from .cargo import get_cargo_ip_from_netaddress, delete_syncdown_job
from .utils import handle_docker_run_container

logger = logging.getLogger(__name__)


def handle_create_interceptrequest(config: ClientConfiguration, body):
    ireq = config.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
        namespace=config.NAMESPACE,
        body=body,
        group="gefyra.dev",
        plural="interceptrequests",
        version="v1",
    )
    return ireq


def handle_delete_interceptrequest(config: ClientConfiguration, name: str) -> bool:
    try:
        ireq = config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object(
            namespace=config.NAMESPACE,
            name=name,
            group="gefyra.dev",
            plural="interceptrequests",
            version="v1",
        )
        delete_syncdown_job(config, ireq["metadata"]["name"])
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.debug(f"InterceptRequest {name} not found")
        else:
            logger.debug("Error removing InterceptRequest: " + str(e))
        return False


def get_all_interceptrequests(config: ClientConfiguration) -> list:
    try:
        ireq_list = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            namespace=config.NAMESPACE,
            group="gefyra.dev",
            plural="interceptrequests",
            version="v1",
        )
        if ireq_list:
            return list(ireq_list.get("items"))
        else:
            return []
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error getting InterceptRequests: " + str(e))


def remove_interceptrequest_remainder(config: ClientConfiguration):
    try:
        ireq_list = get_all_interceptrequests(config)
        if ireq_list:
            logger.debug(f"Removing {len(ireq_list)} InterceptRequests remainder")
            # if there are running intercept requests clean them up
            for ireq in ireq_list:
                handle_delete_interceptrequest(config, ireq["metadata"]["name"])
                sleep(1)
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error removing remainder InterceptRequests: " + str(e))


def get_ireq_body(
    config: ClientConfiguration,
    name: str,
    destination_ip,
    destination_port,
    target_pod,
    target_namespace,
    target_container,
    target_container_port,
    sync_down_directories,
):
    return {
        "apiVersion": "gefyra.dev/v1",
        "kind": "InterceptRequest",
        "metadata": {
            "name": name,
            "namspace": config.NAMESPACE,
        },
        "destinationIP": destination_ip,
        "destinationPort": destination_port,
        "targetPod": target_pod,
        "targetNamespace": target_namespace,
        "targetContainer": target_container,
        "targetContainerPort": target_container_port,
        "syncDownDirectories": sync_down_directories,
    }


def deploy_app_container(
    config: ClientConfiguration,
    image: str,
    name: str = None,
    command: str = None,
    volumes: dict = None,
    ports: dict = None,
    env: dict = None,
    auto_remove: bool = None,
    dns_search: str = "default",
) -> Container:

    gefyra_net = config.DOCKER.networks.get(config.NETWORK_NAME)

    net_add = gefyra_net.attrs["IPAM"]["Config"][0]["Subnet"].split("/")[0]
    cargo_ip = get_cargo_ip_from_netaddress(net_add)
    all_kwargs = {
        "network": config.NETWORK_NAME,
        "name": name,
        "command": command,
        "volumes": volumes,
        "ports": ports,
        "detach": True,
        "dns": [config.STOWAWAY_IP],
        "dns_search": [dns_search],
        "auto_remove": auto_remove,
        "environment": env,
    }
    not_none_kwargs = {k: v for k, v in all_kwargs.items() if v is not None}
    p = multiprocessing.Process(
        target=patch_container_gateway, args=(config, name, cargo_ip)
    )
    p.start()
    try:
        container = handle_docker_run_container(config, image, **not_none_kwargs)
    except docker.errors.APIError as e:
        p.kill()
        raise e
    else:
        p.join()

    return container


def patch_container_gateway(
    config: ClientConfiguration, container_name: str, gateway_ip
) -> None:
    """
    This function will be called as a subprocess
    :param config: a ClientConfiguration
    :param container_name: the name of the container to be patched
    :param gateway_ip: the target ip address of the gateway
    :return: None
    """
    logger.debug("Waiting for the gateway patch to be applied")
    for event in config.DOCKER.events(filters={"container": container_name}):
        event_dict = json.loads(event.decode("utf-8"))
        if event_dict["status"] == "start":
            # subprocess.call([os.path.join(rdir, "cargo/route_setting.sh"), container_name, gateway_ip], timeout=10)
            # return
            pid = subprocess.check_output(
                ["docker", "inspect", "--format", "{{.State.Pid}}", container_name]
            )
            pid = pid.decode().strip()
            logger.debug("This pid: " + str(pid))
            code = subprocess.call(
                ["sudo", "nsenter", "-n", "-t", pid, "ip", "route", "del", "default"]
            )
            if code == 0:
                code = subprocess.call(
                    [
                        "sudo",
                        "nsenter",
                        "-n",
                        "-t",
                        pid,
                        "ip",
                        "route",
                        "add",
                        "default",
                        "via",
                        gateway_ip,
                    ]
                )
                if code == 0:
                    logger.debug(f"Gateway patch applied to '{container_name}'")
            else:
                logger.error(
                    f"Gateway patch could not be applied to '{container_name}'"
                )
            return
