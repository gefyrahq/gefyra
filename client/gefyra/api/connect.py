import logging
import os
import platform
import sys
import time
from typing import Dict, List

from gefyra.configuration import default_configuration, get_gefyra_config_location
from gefyra.local import CONNECTION_NAME_LABEL
from gefyra.local.cargo import (
    create_cargo_container,
    create_wireguard_config,
    get_cargo_ip_from_netaddress,
    probe_wireguard_connection,
)
from gefyra.local.networking import create_gefyra_network
from gefyra.local.utils import (
    handle_docker_create_container,
    handle_docker_get_or_create_container,
)
from gefyra.types import GefyraClient, GefyraClientState


from . import down


logger = logging.getLogger(__name__)


def connect(client: GefyraClient, config=default_configuration) -> bool:
    import kubernetes
    import docker

    # 1. get or create a dedicated gefyra network with suffix (from connection name)
    # 2. try activate the GeyfraClient in the cluster by submitting the subnet (see: operator/tests/e2e/test_connect_clients.py)
    # -> feature to add to the GefyraClient type (see: client/gefyra/types.py)
    # 3. get the wireguard config from the GefyraClient
    # 4. Deploy Cargo with the wireguard config (see code from here: operator/tests/e2e/utils.py)
    _retry = 0
    while _retry < 5:
        gefyra_network = create_gefyra_network(config, suffix=config.CONNECTION_NAME)
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
    # place wireguard config to disk, mount it as
    wg_conf = os.path.join(
        get_gefyra_config_location(config), f"{config.CONNECTION_NAME}.conf"
    )
    if config.CARGO_ENDPOINT is None:
        config.CARGO_ENDPOINT = client.provider_config.pendpoint

    with open(wg_conf, "w") as f:
        f.write(
            create_wireguard_config(
                client.provider_config, config.CARGO_ENDPOINT, config.WIREGUARD_MTU
            )
        )

    if sys.platform == "win32" or "microsoft" in platform.release().lower():
        image_name_and_tag = f"{config.CARGO_IMAGE}-win32"
    else:
        image_name_and_tag = config.CARGO_IMAGE

    # config.DOCKER.images.pull(image_name_and_tag)
    # "user specified IP address is supported only when connecting to networks with user configured subnets"
    cargo_ip_address = get_cargo_ip_from_netaddress(
        gefyra_network.attrs["IPAM"]["Config"][0]["Subnet"]
    )
    cargo_container = None
    try:
        cargo_container = handle_docker_get_or_create_container(
            config,
            f"{config.CARGO_CONTAINER_NAME}",
            image_name_and_tag,
            detach=True,
            # auto_remove=True,
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


def disconnect(client: GefyraClient, config=default_configuration) -> bool:
    import docker

    gefyra_network = create_gefyra_network(config, suffix=config.CONNECTION_NAME)
    try:
        cargo_container = config.DOCKER.containers.get(
            f"{config.CARGO_CONTAINER_NAME}",
        )
        cargo_container.stop()
    except docker.errors.NotFound:
        pass
    client.deactivate_connection()
    return True


def list_connections(config=default_configuration) -> List[Dict[str, str]]:
    from gefyra.local import CARGO_LABEL, CONNECTION_NAME_LABEL, VERSION_LABEL

    result = []
    containers = config.DOCKER.containers.list(
        all=True, filters={"label": f"{CARGO_LABEL[0]}={CARGO_LABEL[1]}"}
    )
    for cargo_container in containers:
        result.append(
            {
                "name": cargo_container.labels.get(CONNECTION_NAME_LABEL, "unknown"),
                "version": cargo_container.labels.get(VERSION_LABEL, "unknown"),
                "created": cargo_container.attrs.get("Created", "unknown"),
                "status": cargo_container.status,
            }
        )
    return result
