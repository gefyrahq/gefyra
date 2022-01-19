import json
import logging
import multiprocessing
import subprocess
from datetime import datetime

import docker
from docker.models.containers import Container

from gefyra.configuration import ClientConfiguration

from .cargo import get_cargo_ip_from_netaddress
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


def get_ireq_body(
    config: ClientConfiguration,
    destination_ip,
    destination_port,
    target_pod,
    target_namespace,
    target_container,
    target_container_port,
):
    return {
        "apiVersion": "gefyra.dev/v1",
        "kind": "InterceptRequest",
        "metadata": {
            "name": f"{target_container}-ireq-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "namspace": config.NAMESPACE,
        },
        "destinationIP": destination_ip,
        "destinationPort": destination_port,
        "targetPod": target_pod,
        "targetNamespace": target_namespace,
        "targetContainer": target_container,
        "targetContainerPort": target_container_port,
    }


def deploy_app_container(
    config: ClientConfiguration,
    image: str,
    name: str = None,
    command: str = None,
    volumes: dict = None,
    ports: dict = None,
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


def run(
    config: ClientConfiguration,
    destination_ip: str,
    destination_port: str,
    target_pod: str,
    target_container: str,
    target_container_port: str,
    target_namespace: str = "default",
):
    # create ireq
    ireq_body = get_ireq_body(
        destination_ip=destination_ip,
        destination_port=destination_port,
        target_pod=target_pod,
        target_namespace=target_namespace,
        target_container=target_container,
        target_container_port=target_container_port,
    )
    handle_create_interceptrequest(config, ireq_body)


def bridge(
    config: ClientConfiguration,
    app_image,
    destination_ip: str,
    destination_port: str,
    target_pod: str,
    target_container: str,
    target_container_port: str,
    target_namespace: str = "default",
    command=None,
    volumes=None,
    ports=None,
):
    # TODO:
    # # start listening to docker events to change the app containers default route
    # events = client.events(filters={"container": APP_CONTAINER_NAME})
    # loop = asyncio.get_event_loop()
    # loop.create_task(change_container_default_route(events, APP_CONTAINER_NAME, cargo_ip))

    print("gonna deploy app container")
    # deploy app container
    # TODO: add --dns flag
    deploy_app_container(
        app_image,
        name="TODO",
        command=command,
        volumes=volumes,
        ports=ports,
        detach=True,
        remove=True,
        auto_remove=True,
    )

    print("gonna create ireq")
    # create ireq
    ireq_body = get_ireq_body(
        destination_ip=destination_ip,  # TODO: should this be IP of app-container?
        destination_port=destination_port,
        target_pod=target_pod,
        target_namespace=target_namespace,
        target_container=target_container,
        target_container_port=target_container_port,
    )
    print(f"IREQ body: {ireq_body}")
    handle_create_interceptrequest(ireq_body)


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
    # rdir = pathlib.Path(__file__).parent.resolve()
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
            subprocess.call(
                ["sudo", "nsenter", "-n", "-t", pid, "ip", "route", "del", "default"]
            )
            subprocess.call(
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
            return
