import logging

from gefyra.api import bridge
from gefyra.api.run import retrieve_pod_and_container, run
from gefyra.api.utils import is_port_free
from gefyra.cluster.utils import (
    get_container_command,
    get_container_image,
    get_container_ports,
    get_v1pod,
)
from gefyra.configuration import default_configuration

logger = logging.getLogger(__name__)


def reflect(
    workload: str,  # deploy/my-deployment
    namespace: str = "default",
    config=default_configuration,
    do_bridge: bool = False,
    env: list = None,
    command: str = "",
    volumes: dict = None,
    auto_remove: bool = False,
    expose_ports: bool = True,
    image: str = None,
    ports: dict = {},
):
    if expose_ports and ports:
        raise RuntimeError(
            "You cannot specify ports and expose_ports at the same time."
        )

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
            ports[host_port] = port.container_port

    host_ports = ports.keys()
    ports_not_free = []

    for port in host_ports:
        if not is_port_free(port):
            ports_not_free.append(str(port))
    if len(ports_not_free):
        raise RuntimeError(
            f"Following ports are needed for the container to run, but are occupied  \
            on your host system: {', '.join(ports_not_free)}. \
            Please provide a port mapping via --port to overwrite these ports."
        )

    res = run(
        name=name,
        image=image,
        command=command,
        volumes=volumes,
        auto_remove=auto_remove,
        namespace=namespace,
        config=config,
        env_from=workload,
        env=env,
        detach=True,
        ports=ports,
    )

    if do_bridge:
        # TODO bridge
        res = bridge(
            name=name, namespace=namespace, config=config, target=workload, ports=ports
        )
    return res
