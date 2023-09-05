import os
from typing import List, Optional, TYPE_CHECKING
import uuid

from gefyra.configuration import ClientConfiguration, logger
from gefyra.local import (
    BRIDGE_ID_LABEL,
    CLIENT_ID_LABEL,
    CONNECTION_NAME_LABEL,
    CREATED_BY_LABEL,
    ACTIVE_KUBECONFIG_LABEL,
    ACTIVE_KUBECONFIG_CONTEXT_LABEL,
    CARGO_ENDPOINT_LABEL,
    VERSION_LABEL,
    CARGO_LABEL,
)

if TYPE_CHECKING:
    from docker.models.containers import Container


def get_processed_paths(base_path: str, volumes: List[str]) -> Optional[List[str]]:
    if volumes is None:
        return None
    results = []
    for volume in volumes:
        source, target = volume.rsplit(":", 1)
        if not os.path.isabs(source):
            source = os.path.realpath(os.path.join(base_path, source))
        results.append(f"{source}:{target}")
    return results


def handle_docker_get_or_create_container(
    config: ClientConfiguration, name: str, image: str, **kwargs
) -> "Container":
    import docker

    try:
        return config.DOCKER.containers.get(name)
    except docker.errors.NotFound:
        return handle_docker_create_container(config, image, name=name, **kwargs)


def handle_docker_create_container(
    config: ClientConfiguration, image: str, **kwargs
) -> "Container":
    import gefyra.configuration
    import docker

    try:
        config.DOCKER.images.get(image)
    except docker.errors.ImageNotFound:
        repo, tag = image.split(":")
        logger.debug(f"Pulling {repo}:{tag} image.")
        config.DOCKER.images.pull(repository=repo, tag=tag)

    return config.DOCKER.containers.create(
        image,
        labels={
            CREATED_BY_LABEL[0]: CREATED_BY_LABEL[1],
            CARGO_LABEL[0]: CARGO_LABEL[1],
            ACTIVE_KUBECONFIG_LABEL: config.KUBE_CONFIG_FILE,
            ACTIVE_KUBECONFIG_CONTEXT_LABEL: config.KUBE_CONTEXT,
            CARGO_ENDPOINT_LABEL: config.CARGO_ENDPOINT,
            CONNECTION_NAME_LABEL: config.CONNECTION_NAME,
            CLIENT_ID_LABEL: config.CLIENT_ID,
            VERSION_LABEL: gefyra.configuration.__VERSION__,
        },
        **kwargs,
    )


def handle_docker_run_container(
    config: ClientConfiguration, image: str, **kwargs
) -> "Container":
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
            BRIDGE_ID_LABEL: uuid.uuid4().hex,
        },
        **kwargs,
    )


def get_connection_from_kubeconfig(kubeconfig: Optional[str] = None) -> Optional[str]:
    import yaml

    if kubeconfig:
        _file = kubeconfig
    else:
        from kubernetes.config.kube_config import KUBE_CONFIG_DEFAULT_LOCATION
        from pathlib import Path

        _file = str(Path(KUBE_CONFIG_DEFAULT_LOCATION).expanduser())

    try:
        with open(_file, "r") as kubeconfig_file:
            kubecfg = yaml.safe_load(kubeconfig_file)
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
        logger.error(
            f"Could not load Gefyra --host and --port from kubeconfig due to: {e}"
        )
        return None


def compose_kubeconfig_for_serviceaccount(
    server: str, ca: str, namespace: str, token: str
):
    return f"""apiVersion: v1
kind: Config
clusters:
  - name: default-cluster
    cluster:
      certificate-authority-data: {ca}
      server: {server}
contexts:
  - name: default-context
    context:
      cluster: default-cluster
      namespace: {namespace}
      user: default-user
current-context: default-context
users:
  - name: default-user
    user:
      token: {token}
    """
