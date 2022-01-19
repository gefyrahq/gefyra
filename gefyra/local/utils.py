import os
from datetime import datetime

from docker.models.containers import Container

from gefyra.cluster.utils import decode_secret
from gefyra.configuration import ClientConfiguration


def get_cargo_connection_data(config: ClientConfiguration):
    cargo_connection_secret = config.K8S_CORE_API.read_namespaced_secret(
        name="gefyra-cargo-connection", namespace=config.NAMESPACE
    )
    return decode_secret(cargo_connection_secret.data)


def build_cargo_image(
    config: ClientConfiguration,
    wireguard_ip: str,
    private_key: str,
    dns: str,
    public_key: str,
    endpoint: str,
    allowed_ips: str,
):
    build_args = {
        "ADDRESS": wireguard_ip,
        "PRIVATE_KEY": private_key,
        "DNS": dns,
        "PUBLIC_KEY": public_key,
        "ENDPOINT": endpoint,
        "ALLOWED_IPS": allowed_ips,
    }
    tag = f"{config.CARGO_CONTAINER_NAME}:{datetime.now().strftime('%Y%m%d%H%M%S')}"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cargo")
    image, build_logs = config.DOCKER.images.build(
        path=path, rm=True, forcerm=True, buildargs=build_args, tag=tag
    )
    return image, build_logs


def get_container_ip(
    config: ClientConfiguration, container: Container = None, container_id: str = None
) -> str:
    assert container or container_id, "Either container or id must be specified!"

    # TODO handle exceptions
    if container:
        # we might need to reload attrs
        container.reload()
    else:
        container = config.DOCKER.containers.get(container_id)
    return container.attrs["NetworkSettings"]["Networks"][config.NETWORK_NAME][
        "IPAddress"
    ]


def handle_docker_stop_container(
    config: ClientConfiguration, container: Container = None, container_id: str = None
):
    """Stop docker container, either `container` or `container_id` must be specified.

    :param config: gefyra.configuration.ClientConfiguration instance
    :param container: docker.models.containers.Container instance
    :param container_id: id or name of a docker container

    :raises AssertionError: if neither container nor container_id is specified
    :raises docker.errors.APIError: when stopping of container fails
    """
    assert container or container_id, "Either container or id must be specified!"
    if not container:
        container = config.DOCKER.containers.get(container_id)

    container.stop()


def handle_docker_remove_container(
    config: ClientConfiguration, container: Container = None, container_id: str = None
):
    """Stop docker container, either `container` or `container_id` must be specified.

    :param config: gefyra.configuration.ClientConfiguration instance
    :param container: docker.models.containers.Container instance
    :param container_id: id or name of a docker container

    :raises AssertionError: if neither container nor container_id is specified
    :raises docker.errors.APIError: when removing of container fails
    """
    assert container or container_id, "Either container or id must be specified!"
    if not container:
        container = config.DOCKER.containers.get(container_id)

    container.remove(force=True)


def handle_docker_create_container(
    config: ClientConfiguration, image: str, **kwargs
) -> Container:
    return config.DOCKER.containers.create(image, **kwargs)


def handle_docker_run_container(
    config: ClientConfiguration, image: str, **kwargs
) -> Container:
    # if detach=True is in kwargs, this will return a container; otherwise the container logs (see
    # https://docker-py.readthedocs.io/en/stable/containers.html#docker.models.containers.ContainerCollection.run)
    # TODO: handle exception(s):
    # docker.errors.ContainerError – If the container exits with a non-zero exit code and detach is False.
    # docker.errors.ImageNotFound – If the specified image does not exist.
    # docker.errors.APIError – If the server returns an error.
    return config.DOCKER.containers.run(image, **kwargs)
