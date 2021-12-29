import logging
import os
import sys
from datetime import datetime

import docker
import kubernetes as k8s
from docker.models.containers import Container

from .utils import build_cargo_image, get_cargo_connection_data

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

k8s.config.load_kube_config()
custom_object_api = k8s.client.CustomObjectsApi()
client = docker.from_env()
NAMESPACE = os.getenv("GEFYRA_NAMESPACE", "gefyra")
ENDPOINT = os.getenv("GEFYRA_CARGO_ENDPOINT", "172.17.0.1:31820")
CARGO_CONTAINER_NAME = os.getenv("GEFYRA_CARGO_CONTAINER_NAME", "cargo")


def handle_docker_run_container(image, **kwargs):
    # if detach=True is in kwargs, this will return a container; otherwise the container logs (see
    # https://docker-py.readthedocs.io/en/stable/containers.html#docker.models.containers.ContainerCollection.run)
    # TODO: handle exception(s):
    # docker.errors.ContainerError – If the container exits with a non-zero exit code and detach is False.
    # docker.errors.ImageNotFound – If the specified image does not exist.
    # docker.errors.APIError – If the server returns an error.
    return client.containers.run(image, **kwargs)


def handle_docker_stop_container(container: Container = None, container_id: str = None):
    """Stop docker container, either `container` or `container_id` must be specified.

    :param container: docker.models.containers.Container instance
    :param container_id: id or name of a docker container

    :raises AssertionError: if neither container nor container_id is specified
    :raises docker.errors.APIError: when stopping of container fails
    """
    assert container or container_id, "Either container or id must be specified!"
    if not container:
        container = client.containers.get(container_id)

    container.stop()


def handle_create_interceptrequest(body):
    custom_object_api.create_namespaced_custom_object(
        namespace=NAMESPACE,
        body=body,
        group="gefyra.dev",
        plural="interceptrequests",
        version="v1",
    )
    logger.info("Interceptrequest created")


def get_ireq_body(
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
            "namspace": NAMESPACE,
        },
        "destinationIP": destination_ip,
        "destinationPort": destination_port,
        "targetPod": target_pod,
        "targetNamespace": target_namespace,
        "targetContainer": target_container,
        "targetContainerPort": target_container_port,
    }


def deploy_cargo_container() -> Container:
    # get connection data from secret
    cargo_connection_data = get_cargo_connection_data()
    wireguard_ip = f"{cargo_connection_data['Interface.Address']}/32"
    private_key = cargo_connection_data["Interface.PrivateKey"]
    dns = f"{cargo_connection_data['Interface.DNS']} {NAMESPACE}.svc.cluster.local"
    public_key = cargo_connection_data["Peer.PublicKey"]
    endpoint = ENDPOINT
    allowed_ips = cargo_connection_data["Peer.AllowedIPs"]

    # build image
    image, build_logs = build_cargo_image(
        wireguard_ip=wireguard_ip,
        private_key=private_key,
        dns=dns,
        public_key=public_key,
        endpoint=endpoint,
        allowed_ips=allowed_ips,
    )

    # we only have one tag
    image_name_and_tag = image.tags[0]
    # tag is a timestamp
    # we make the containers name unique in case multiple different cargo containers shall run
    container_name = f"{CARGO_CONTAINER_NAME}_{image_name_and_tag.split(':')[-1]}"
    # run image
    container = handle_docker_run_container(
        image_name_and_tag,
        detach=True,
        name=container_name,
        network_mode="bridge",
        auto_remove=True,
        remove=True,
    )

    return container


def deploy_app_container(
    image: str,
    network_container_id: str,
    command: str = None,
    volumes: dict = None,
    ports: dict = None,
    tty: bool = None,
):
    all_kwargs = {
        "image": image,
        "network_mode": f"container:{network_container_id}",
        "command": command,
        "volumes": volumes,
        "ports": ports,
        "tty": tty,
    }
    not_none_kwargs = {k: v for k, v in all_kwargs.items() if v is not None}

    logs = handle_docker_run_container(**not_none_kwargs)

    return logs


def run(
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
    handle_create_interceptrequest(ireq_body)


def bridge(
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
    tty=None,
):
    # deploy cargo container
    cargo_container = deploy_cargo_container()

    # deploy app container
    deploy_app_container(
        app_image,
        network_container_id=cargo_container.id,
        command=command,
        volumes=volumes,
        ports=ports,
        tty=tty,
    )

    # create ireq
    ireq_body = get_ireq_body(
        destination_ip=destination_ip,
        destination_port=destination_port,
        target_pod=target_pod,
        target_namespace=target_namespace,
        target_container=target_container,
        target_container_port=target_container_port,
    )
    handle_create_interceptrequest(ireq_body)
