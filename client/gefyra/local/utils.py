import argparse
import os
from datetime import datetime
from typing import List, Optional

from docker.models.containers import Container

from gefyra.cluster.utils import decode_secret
from gefyra.configuration import ClientConfiguration, logger
from gefyra.local.cargoimage.Dockerfile import get_dockerfile
from gefyra.local import CREATED_BY_LABEL


def set_gefyra_network_from_cargo(config) -> ClientConfiguration:
    from docker.errors import NotFound

    try:
        cargo_container = config.DOCKER.containers.get(config.CARGO_CONTAINER_NAME)
        networks = list(cargo_container.attrs["NetworkSettings"]["Networks"].keys())
        try:
            networks.remove("bridge")
        except ValueError:
            pass
        config.NETWORK_NAME = networks[0]
    except NotFound:
        raise RuntimeError("Gefyra Cargo not running. Please run 'gefyra up' first.")
    except KeyError:
        raise RuntimeError(
            "Gefyra Cargo is not configured properly. "
            "Please set up Gefyra again with 'gefyra down' and 'gefyra up'."
        )
    return config


def get_processed_paths(base_path: str, volumes: List[str]) -> Optional[List[str]]:
    if volumes is None:
        return None
    results = []
    for volume in volumes:
        source, target = volume.split(":")
        if not os.path.isabs(source):
            source = os.path.realpath(os.path.join(base_path, source))
        results.append(f"{source}:{target}")
    return results


def get_cargo_connection_data(config: ClientConfiguration):
    cargo_connection_secret = config.K8S_CORE_API.read_namespaced_secret(
        name="gefyra-cargo-connection", namespace=config.NAMESPACE
    )
    return decode_secret(cargo_connection_secret.data)


def build_cargo_image(
    config: ClientConfiguration,
    wireguard_ip: str,
    mtu: str,
    private_key: str,
    dns: str,
    public_key: str,
    endpoint: str,
    allowed_ips: str,
):
    build_args = {
        "ADDRESS": wireguard_ip,
        "MTU": str(mtu),
        "PRIVATE_KEY": private_key,
        "DNS": dns,
        "PUBLIC_KEY": public_key,
        "ENDPOINT": endpoint,
        "ALLOWED_IPS": allowed_ips,
    }
    tag = f"{config.CARGO_CONTAINER_NAME}:{datetime.now().strftime('%Y%m%d%H%M%S')}"
    # check for Cargo updates
    config.DOCKER.images.pull(config.CARGO_IMAGE)
    # build this instance
    _Dockerfile = get_dockerfile(config.CARGO_IMAGE)
    image, build_logs = config.DOCKER.images.build(
        fileobj=_Dockerfile, rm=True, forcerm=True, buildargs=build_args, tag=tag
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
    return config.DOCKER.containers.create(
        image,
        labels={
            CREATED_BY_LABEL[0]: CREATED_BY_LABEL[1],
        },
        **kwargs,
    )


def handle_docker_run_container(
    config: ClientConfiguration, image: str, **kwargs
) -> Container:
    # if detach=True is in kwargs, this will return a container; otherwise the container logs (see
    # https://docker-py.readthedocs.io/en/stable/containers.html#docker.models.containers.ContainerCollection.run)
    # TODO: handle exception(s):
    # docker.errors.ContainerError – If the container exits with a non-zero exit code and detach is False.
    # docker.errors.ImageNotFound – If the specified image does not exist.
    # docker.errors.APIError – If the server returns an error.
    return config.DOCKER.containers.run(
        image,
        labels={
            CREATED_BY_LABEL[0]: CREATED_BY_LABEL[1],
        },
        **kwargs,
    )


def get_connection_from_kubeconfig() -> Optional[str]:
    from kubernetes.config.kube_config import KUBE_CONFIG_DEFAULT_LOCATION
    from pathlib import Path
    import yaml

    try:
        with open(Path(KUBE_CONFIG_DEFAULT_LOCATION).expanduser(), "r") as kubeconfig:
            kubecfg = yaml.safe_load(kubeconfig)
        active_ctx = next(
            filter(
                lambda x: x["name"] == kubecfg["current-context"], kubecfg["contexts"]
            )
        )
        if gefyra_connection := active_ctx.get("gefyra"):
            return gefyra_connection
        else:
            return None
    except Exception as e:  # noqa
        logger.error(f"Could not load Gefyra --endpoint from kubeconfig due to: {e}")
        return None


class PortMappingParser(argparse.Action):
    """Adapted from https://stackoverflow.com/questions/29986185/python-argparse-dict-arg"""

    def parse_split(self, split):
        # port - port
        res = {}
        if len(split) == 2:
            res[split[1]] = split[0]
            return res
        else:
            raise ValueError

    def __call__(self, parser, namespace, values, option_string=None):
        my_dict = {}
        try:
            for kv in values.split(","):
                res = kv.split(":")
                my_dict.update(self.parse_split(res))
        except Exception:
            logger.error(
                "Invalid port mapping. Example valid port mapping: 8080:8081 (<ip>:host_port:container_port)."
            )
            exit(1)
        setattr(namespace, self.dest, my_dict)


class IpPortMappingParser(PortMappingParser):
    def parse_split(self, split):
        # port - port
        res = {}
        if len(split) == 2:
            res[split[1]] = split[0]
            return res
        elif len(split) == 3:
            res[split[2]] = (split[0], split[1])
            return res
        else:
            raise ValueError
