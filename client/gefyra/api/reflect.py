from gefyra.api import bridge
from gefyra.api.run import retrieve_pod_and_container, run
from gefyra.cluster.utils import get_container_command, get_container_image, get_container_ports, get_v1pod
from gefyra.configuration import default_configuration

def reflect(
        workload: str, # deploy/my-deployment
        namespace: str = "default",
        config=default_configuration,
        do_bridge: bool = False,
        env: list = None,
        command: str = "",
        volumes: dict = None,
        auto_remove: bool = False,
        expose_ports: bool = True
        # TODO adapt port mapping in case it's occupied
    ):

    name = f"gefyra-reflect-{namespace}-{workload.replace('/', '-')}"
    pod_name, container_name = retrieve_pod_and_container(workload, namespace, config)
    ports = {}

    pod = get_v1pod(config=config, pod_name=pod_name, namespace=namespace)

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
        ports=ports
    )

    if do_bridge:
        # TODO bridge
        res = bridge(
            name=name,
            namespace=namespace,
            config=config,
            target=workload,
            ports=ports
        )
    return res
