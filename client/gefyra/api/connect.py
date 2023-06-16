import base64
import logging
import os
from pathlib import Path
import time
from typing import IO, List, Optional
from gefyra.api.clients import get_client
from .utils import stopwatch

from gefyra.configuration import ClientConfiguration, get_gefyra_config_location
from gefyra.local.cargo import (
    create_wireguard_config,
    get_cargo_ip_from_netaddress,
    probe_wireguard_connection,
)
from gefyra.local.networking import get_or_create_gefyra_network
from gefyra.local.utils import (
    compose_kubeconfig_for_serviceaccount,
    handle_docker_get_or_create_container,
)
from gefyra.types import GefyraClientConfig, GefyraClientState, GefyraConnectionItem


logger = logging.getLogger(__name__)


@stopwatch
def connect(connection_name: str, client_config: Optional[IO]) -> bool:
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
            raise RuntimeError(
                "Connection is not yet created and no client configuration has been provided"
            )
        logger.debug(f"Creating new connection {connection_name}")
        file_str = client_config.read()
        client_config.close()
        gclient_conf = GefyraClientConfig.from_json_str(file_str)
        client = get_client(gclient_conf.client_id, connection_name=connection_name)
        loc = os.path.join(
            get_gefyra_config_location(),
            f"{connection_name}.yaml",
        )
        # this kubeconfig is being used by the client to operate in the cluster
        kubeconfig_str = compose_kubeconfig_for_serviceaccount(
            gclient_conf.kubernetes_server,
            gclient_conf.ca_crt,
            "gefyra",
            base64.b64decode(gclient_conf.token).decode("utf-8"),
        )
        with open(loc, "w") as f:
            f.write(kubeconfig_str)
            logger.info(f"Client kubeconfig saved to {loc}")

        config = ClientConfiguration(
            connection_name=connection_name,
            kube_config_file=Path(loc),
            client_id=gclient_conf.client_id,
            cargo_endpoint_host=gclient_conf.gefyra_server.split(":")[0],
            cargo_endpoint_port=gclient_conf.gefyra_server.split(":")[1],
            cargo_container_name=f"gefyra-cargo-{connection_name}",
        )

    _retry = 0
    while _retry < 5:
        gefyra_network = get_or_create_gefyra_network(
            config, suffix=config.CONNECTION_NAME
        )
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
        raise RuntimeError("Could not activate connection") from None

    # busy wait for the client to enter the ACTIVE state
    _i = 0
    while _i < config.CONNECTION_TIMEOUT:
        if client.state == GefyraClientState.ACTIVE:
            break
        else:
            _i += 1
            time.sleep(0.5)
    else:
        raise RuntimeError("Could not activate connection") from None
    client.update()

    # since this connection was (re)activated, save the current wireguard config (again)
    wg_conf = os.path.join(
        get_gefyra_config_location(), f"{config.CONNECTION_NAME}.conf"
    )
    if not client.provider_config:
        raise RuntimeError("Could not get provider config for client") from None

    if config.CARGO_ENDPOINT is None:
        config.CARGO_ENDPOINT = client.provider_config.pendpoint

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
            logger.debug(f"Cargo gefyra net ip address: {cargo_ip_address}")
            gefyra_network.connect(cargo_container, ipv4_address=cargo_ip_address)
        cargo_container.start()
        time.sleep(1)
    except docker.errors.APIError as e:
        try:
            cargo_container and cargo_container.remove()
        except docker.errors.APIError:
            pass
        raise RuntimeError(f"Could not start Cargo container: {e}") from None

    # Confirm the wireguard connection working

    probe_wireguard_connection(config)
    return True


@stopwatch
def disconnect(connection_name: str) -> bool:
    import docker

    config = ClientConfiguration(connection_name=connection_name)
    client = get_client(config.CLIENT_ID, connection_name=connection_name)
    get_or_create_gefyra_network(config, suffix=config.CONNECTION_NAME)
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
                probe_wireguard_connection(
                    ClientConfiguration(cargo_container_name=cargo_container.name)
                )
                established = True
            except RuntimeError:
                established = False
        else:
            established = False
        result.append(
            GefyraConnectionItem(
                **{
                    "name": cargo_container.labels.get(
                        CONNECTION_NAME_LABEL, "unknown"
                    ),
                    "version": cargo_container.labels.get(VERSION_LABEL, "unknown"),
                    "created": cargo_container.attrs.get("Created", "unknown"),
                    "status": cargo_container.status if established else "error",
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
    except:  # noqa E722
        pass
    try:
        cargo_container = config.DOCKER.containers.get(
            f"{config.CARGO_CONTAINER_NAME}",
        )
        cargo_container.remove(force=True)
        gefyra_network = config.DOCKER.networks.get(config.NETWORK_NAME)
        gefyra_network.remove()
    except docker.errors.NotFound:
        pass
    try:
        config.DOCKER.networks.get(f"{config.NETWORK_NAME}-{connection_name}").remove()
    except docker.errors.NotFound:
        pass
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
