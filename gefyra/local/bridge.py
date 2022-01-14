import logging
import multiprocessing
from datetime import datetime

from gefyra.configuration import ClientConfiguration

from .utils import handle_docker_run_container, patch_container_gateway

logger = logging.getLogger(__name__)


def handle_create_interceptrequest(config: ClientConfiguration, body):
    config.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
        namespace=config.NAMESPACE,
        body=body,
        group="gefyra.dev",
        plural="interceptrequests",
        version="v1",
    )
    logger.info("Interceptrequest created")


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
):

    gefyra_net = config.DOCKER.networks.get(config.NETWORK_NAME)

    net_add = gefyra_net.attrs["IPAM"]["Config"][0]["Subnet"].split("/")[0]
    cargo_ip = ".".join(net_add.split(".")[:3]) + ".149"
    all_kwargs = {
        "network": config.NETWORK_NAME,
        "name": name,
        "command": command,
        "volumes": volumes,
        "ports": ports,
        "detach": True,
        "dns": ["192.168.99.1"],
        "auto_remove": auto_remove,
    }
    not_none_kwargs = {k: v for k, v in all_kwargs.items() if v is not None}
    p = multiprocessing.Process(target=patch_container_gateway, args=(config, name, cargo_ip))
    p.start()
    container = handle_docker_run_container(config, image, **not_none_kwargs)
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
