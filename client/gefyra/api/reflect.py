import logging
from typing import Dict, List, Optional

from gefyra.api.bridge import bridge
from gefyra.api.run import run
from gefyra.api.utils import is_port_free
from gefyra.cluster.utils import (
    get_container_command,
    get_container_image,
    get_container_ports,
    get_v1pod,
    retrieve_pod_and_container,
)
from gefyra.configuration import ClientConfiguration

logger = logging.getLogger(__name__)


def _check_ports(host_ports):
    ports_not_free = []
    for port in host_ports:
        if not is_port_free(port):
            ports_not_free.append(str(port))
    if len(ports_not_free):
        raise RuntimeError(
            "Following ports are needed for the container to run, but are occupied    "
            f"          on your host system: {', '.join(ports_not_free)}.            "
            " Please provide a port mapping via --port to overwrite these ports."
        )


def reflect(
    workload: str,  # deploy/my-deployment
    namespace: str = "default",
    do_bridge: bool = False,
    env: Optional[List] = None,
    command: str = "",
    volumes: Optional[Dict] = None,
    auto_remove: bool = False,
    expose_ports: bool = True,
    image: str = "",
    ports: Optional[Dict] = None,
    connection_name: str = "",
):
    config = ClientConfiguration(connection_name=connection_name)
    if expose_ports and ports:
        raise RuntimeError(
            "You cannot specify ports and expose_ports at the same time."
        )
    if not ports:
        ports = {}

    name = f"gefyra-reflect-{namespace}-{workload.replace('/', '-')}"
    pod_name, container_name = retrieve_pod_and_container(workload, namespace, config)

    pod = get_v1pod(config=config, pod_name=pod_name, namespace=namespace)
    if not image:
        image = get_container_image(pod, container_name)
    if not command:
        command = get_container_command(pod, container_name)

    if expose_ports:
        container_ports = get_container_ports(pod, container_name)
        for port in container_ports:
            host_port = ""
            if not port.host_port:
                host_port = port.container_port
            ports[port.container_port] = host_port

    host_ports = ports.values()

    _check_ports(host_ports)

    res = run(
        name=name,
        image=image,
        command=command,
        volumes=volumes,
        auto_remove=auto_remove,
        namespace=namespace,
        connection_name=connection_name,
        env_from=workload,
        env=env,
        detach=True,
        ports=ports,
    )

    if do_bridge:
        res = bridge(
            name=name,
            namespace=namespace,
            target=workload,
            ports=ports,
            connection_name=connection_name,
            wait=True,
        )
    return res
