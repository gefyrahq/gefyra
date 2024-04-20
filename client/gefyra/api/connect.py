import base64
import logging
import os
from pathlib import Path
import socket
import time

from typing import IO, List, Optional, TYPE_CHECKING
from gefyra.api.clients import get_client
from gefyra.exceptions import GefyraConnectionError
from gefyra.local.clients import handle_get_gefyraclient
from gefyra.local.minikube import detect_minikube_config
from .utils import stopwatch

if TYPE_CHECKING:
    from docker.models.networks import Network


from gefyra.configuration import ClientConfiguration, get_gefyra_config_location
from gefyra.local.cargo import (
    create_wireguard_config,
    get_cargo_ip_from_netaddress,
    probe_wireguard_connection,
)
from gefyra.local.networking import get_or_create_gefyra_network, handle_remove_network
from gefyra.local.utils import (
    compose_kubeconfig_for_serviceaccount,
    handle_docker_get_or_create_container,
)
from gefyra.types import (
    GefyraClient,
    GefyraClientConfig,
    GefyraClientState,
    GefyraConnectionItem,
)


logger = logging.getLogger(__name__)


@stopwatch
def connect(  # noqa: C901
    connection_name: str,
    client_config: Optional[IO],
    minikube_profile: Optional[str] = None,
    probe_timeout: int = 60,
) -> bool:
    import kubernetes
    import docker

    cargo_container = None
    # if this connection already exists, just restore it
    if connection_name in [conns.name for conns in list_connections()]:
        logger.debug(f"Restoring exinsting connection {connection_name}")
        config = ClientConfiguration(connection_name=connection_name)
        cargo_container = config.DOCKER.containers.get(config.CARGO_CONTAINER_NAME)
        client = get_client(config.CLIENT_ID, connection_name=config.CONNECTION_NAME)
    else:
        # connection does not exist, so create it
        if client_config is None:
            raise GefyraConnectionError(
                "Connection is not yet created and no client configuration has been provided."
            )
        logger.debug(f"Creating new connection {connection_name}")
        file_str = client_config.read()
        client_config.close()
        gclient_conf = GefyraClientConfig.from_json_str(file_str)

        # this kubeconfig is being used by the client to operate in the cluster
        kubeconfig_str = compose_kubeconfig_for_serviceaccount(
            gclient_conf.kubernetes_server,
            gclient_conf.ca_crt,
            "gefyra",
            base64.b64decode(gclient_conf.token).decode("utf-8"),
        )
        loc = os.path.join(
            get_gefyra_config_location(),
            f"{connection_name}.yaml",
        )
        with open(loc, "w") as f:
            f.write(kubeconfig_str)
            logger.info(f"Client kubeconfig saved to {loc}")

        if minikube_profile:
            logger.debug(f"Minikube profile detected: {minikube_profile}")
            mini_conf = detect_minikube_config(minikube_profile)
            logger.debug(mini_conf)
            gclient_conf.gefyra_server = (
                f"{mini_conf['cargo_endpoint_host']}:{mini_conf['cargo_endpoint_port']}"
            )

        config = ClientConfiguration(
            connection_name=connection_name,
            kube_config_file=Path(loc),
            client_id=gclient_conf.client_id,
            cargo_endpoint_host=gclient_conf.gefyra_server.split(":")[0],
            cargo_endpoint_port=gclient_conf.gefyra_server.split(":")[1],
            cargo_container_name=f"gefyra-cargo-{connection_name}",
        )

        gclient = handle_get_gefyraclient(config, gclient_conf.client_id)
        client = GefyraClient(gclient, config)

        config.CARGO_PROBE_TIMEOUT = probe_timeout

    _retry = 0
    while _retry < 5:
        gefyra_network = get_or_create_gefyra_network(config)
        try:
            client.activate_connection(
                gefyra_network.attrs["IPAM"]["Config"][0]["Subnet"]
            )
            break
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 500:
                logger.debug(f"Could not activate connection, retrying {_retry}/5...")
                # if the given subnet is taken in the cluster (by another client), recreate the network and try again
                # hopefully the IPAM config will give a new subnet
                gefyra_network.remove()
    else:
        raise GefyraConnectionError("Could not activate connection") from None

    # busy wait for the client to enter the ACTIVE state
    _i = 0
    while _i < config.CONNECTION_TIMEOUT:
        if client.state == GefyraClientState.ACTIVE:
            break
        else:
            _i += 1
            time.sleep(0.5)
    else:
        raise GefyraConnectionError("Could not activate connection") from None
    client.update()

    # since this connection was (re)activated, save the current wireguard config (again)
    wg_conf = os.path.join(
        get_gefyra_config_location(), f"{config.CONNECTION_NAME}.conf"
    )
    if not client.provider_config:
        raise GefyraConnectionError(
            "Could not get provider config for client"
        ) from None

    if config.CARGO_ENDPOINT is None:
        config.CARGO_ENDPOINT = client.provider_config.pendpoint
    logger.debug(config.CARGO_ENDPOINT)
    # busy wait to resolve the cargo endpoint, making sure it's actually resolvable from this host
    _i = 0
    while _i < config.CONNECTION_TIMEOUT:
        try:
            socket.gethostbyname_ex(config.CARGO_ENDPOINT.split(":")[0])
            break
        except (socket.gaierror, socket.herror):  # [Errno -2] Name or service not known
            logger.debug(
                f"Could not resolve host '{config.CARGO_ENDPOINT.split(':')[0]}', "
                f"retrying {_i}/{config.CONNECTION_TIMEOUT}..."
            )
            _i += 1
            time.sleep(1)
    else:
        raise GefyraConnectionError(
            f"Cannot resolve host '{config.CARGO_ENDPOINT.split(':')[0]}'."
        ) from None

    with open(wg_conf, "w") as f:
        f.write(
            create_wireguard_config(
                client.provider_config, config.CARGO_ENDPOINT, config.WIREGUARD_MTU
            )
        )

    cargo_ip_address = get_cargo_ip_from_netaddress(
        gefyra_network.attrs["IPAM"]["Config"][0]["Subnet"]
    )

    try:
        if not cargo_container:
            cargo_container = handle_docker_get_or_create_container(
                config,
                f"{config.CARGO_CONTAINER_NAME}",
                config.CARGO_IMAGE,
                detach=True,
                cap_add=["NET_ADMIN"],
                privileged=True,
                volumes=[
                    "/var/run/docker.sock:/var/run/docker.sock",
                    f"{wg_conf}:/config/wg0.conf",
                ],
                pid_mode="host",
            )

            if minikube_profile:
                mini_conf = detect_minikube_config(minikube_profile)
                if mini_conf["network_name"]:
                    logger.debug("Joining minikube network")
                    minikube_net: "Network" = config.DOCKER.networks.get(
                        mini_conf["network_name"]
                    )
                    minikube_net.connect(cargo_container)
            logger.debug(f"Cargo gefyra net ip address: {cargo_ip_address}")
            gefyra_network.connect(cargo_container, ipv4_address=cargo_ip_address)
        cargo_container.start()
        time.sleep(1)
    except docker.errors.APIError as e:
        try:
            cargo_container and cargo_container.remove()
        except docker.errors.APIError:
            pass
        raise GefyraConnectionError(f"Could not start Cargo container: {e}") from None

    # Confirm the wireguard connection working
    logger.debug("Checking wireguard connection")
    probe_wireguard_connection(config)
    return True


@stopwatch
def disconnect(connection_name: str) -> bool:
    import docker

    config = ClientConfiguration(connection_name=connection_name)
    client = get_client(config.CLIENT_ID, connection_name=connection_name)
    get_or_create_gefyra_network(config)
    try:
        cargo_container = config.DOCKER.containers.get(
            f"{config.CARGO_CONTAINER_NAME}",
        )
        cargo_container.stop()
    except docker.errors.NotFound:
        pass
    client.deactivate_connection()
    return True


@stopwatch
def list_connections() -> List[GefyraConnectionItem]:
    from gefyra.local import CARGO_LABEL, CONNECTION_NAME_LABEL, VERSION_LABEL

    config = ClientConfiguration()
    result = []
    containers = config.DOCKER.containers.list(
        all=True, filters={"label": f"{CARGO_LABEL[0]}={CARGO_LABEL[1]}"}
    )
    for cargo_container in containers:
        if cargo_container.status == "running":
            try:
                config = ClientConfiguration(cargo_container_name=cargo_container.name)
                config.CARGO_PROBE_TIMEOUT = 1  # don't wait too long for the probe
                probe_wireguard_connection(config)
                state = "running"
            except GefyraConnectionError:
                state = "error"
        else:
            state = "stopped"
        result.append(
            GefyraConnectionItem(
                **{
                    "name": cargo_container.labels.get(
                        CONNECTION_NAME_LABEL, "unknown"
                    ),
                    "version": cargo_container.labels.get(VERSION_LABEL, "unknown"),
                    "created": cargo_container.attrs.get("Created", "unknown"),
                    "status": state,
                }
            )
        )
    return result


@stopwatch
def remove_connection(connection_name: str):
    import docker

    config = ClientConfiguration(connection_name=connection_name)
    try:
        get_client(
            config.CLIENT_ID, connection_name=connection_name
        ).deactivate_connection()
    except Exception as e:  # noqa E722
        logger.debug(e)
        pass
    try:
        cargo_container = config.DOCKER.containers.get(
            f"{config.CARGO_CONTAINER_NAME}",
        )
        cargo_container.remove(force=True)
    except docker.errors.NotFound:
        pass
    handle_remove_network(config)
    try:
        # remove kubeconfig file
        os.remove(os.path.join(get_gefyra_config_location(), f"{connection_name}.yaml"))
    except OSError:
        pass
    try:
        # remove wireguard config file
        os.remove(
            os.path.join(get_gefyra_config_location(), f"{config.CONNECTION_NAME}.conf")
        )
    except OSError:
        pass
