import base64
import logging
import os
from pathlib import Path

from typing import IO, Callable, List, Optional, TYPE_CHECKING
import docker
from gefyra.api.clients import get_client
from gefyra.exceptions import (
    ClientConfigurationError,
    GefyraClientNotFound,
    GefyraConnectionError,
)
from gefyra.local.clients import handle_get_gefyraclient
from gefyra.local.minikube import detect_minikube_config
from .utils import stopwatch

if TYPE_CHECKING:
    pass


from gefyra.configuration import ClientConfiguration, get_gefyra_config_location
from gefyra.local.cargo import (
    probe_wireguard_connection,
)
from gefyra.local.networking import handle_remove_network
from gefyra.local.utils import (
    compose_kubeconfig_for_serviceaccount,
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
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
    minikube_profile: Optional[str] = None,
    mtu: Optional[int] = 1340,
    probe_timeout: int = 60,
    update_callback: Optional[callable] = None,
    cargo_image: Optional[str] = None,
    force: bool = False,
    timeout: int = 60,
) -> bool:
    cargo_container = None
    known_connection = connection_name in [conns.name for conns in list_connections()]
    # if this connection already exists, just restore it
    if known_connection:
        logger.debug(f"Restoring existing connection {connection_name}")
        if update_callback:
            update_callback(f"Restoring existing connection {connection_name}")
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
        if update_callback:
            update_callback(f"Creating new connection '{connection_name}'")
        file_str = client_config.read()
        client_config.close()
        gclient_conf = GefyraClientConfig.from_json_str(file_str)

        if not kubeconfig and gclient_conf.ca_crt and gclient_conf.token:
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
            kubeconfig = loc
            kubecontext = None

        if minikube_profile:
            logger.debug(f"Minikube profile detected: {minikube_profile}")
            mini_conf = detect_minikube_config(minikube_profile)
            logger.debug(mini_conf)
            gclient_conf.gefyra_server = (
                f"{mini_conf['cargo_endpoint_host']}:{mini_conf['cargo_endpoint_port']}"
            )

        config = ClientConfiguration(
            connection_name=connection_name,
            kube_config_file=Path(kubeconfig) if kubeconfig else None,
            kube_context=kubecontext,
            client_id=gclient_conf.client_id,
            cargo_endpoint_host=gclient_conf.gefyra_server.split(":")[0],
            cargo_endpoint_port=gclient_conf.gefyra_server.split(":")[1],
            cargo_container_name=f"gefyra-cargo-{connection_name}",
            wireguard_mtu=(str(mtu) if mtu else None) or gclient_conf.wireguard_mtu,
            cargo_image_url=cargo_image or "",
        )

        gclient = handle_get_gefyraclient(config, gclient_conf.client_id)
        client = GefyraClient(gclient, config)

        config.CARGO_PROBE_TIMEOUT = timeout or probe_timeout

    if (
        not known_connection
        and client._state == GefyraClientState.ACTIVE.value
        and not force
    ):
        logger.error(f"Connection {connection_name} is already active.")
        raise GefyraConnectionError(
            f"Connection {connection_name} is already active. Use --force to reconnect."
        )

    if client._state == GefyraClientState.ACTIVE.value and force:
        update_callback(
            f"Connection {connection_name} is already active, but --force is set, diconnecting client..."
        )
        client.disconnect()
        update_callback(f"Connection {connection_name} reconnecting...")

    return client.connect(
        update_callback=update_callback,
        cargo_container=cargo_container,
        minikube_profile=minikube_profile,
        timeout=timeout,
    )


@stopwatch
def disconnect(
    connection_name: str,
    nowait: bool = False,
    update_callback: Callable[[str], None] | None = None,
) -> bool:
    config = ClientConfiguration(connection_name=connection_name)
    if update_callback:
        update_callback(f"Disconnecting Gefyra client '{config.CLIENT_ID}'...")
    if not config.CLIENT_ID:
        raise ClientConfigurationError(
            f"Could not determine client's ID for connection '{connection_name}'. Is gefyra cargo running?"
        )

    client = get_client(config.CLIENT_ID, connection_name=connection_name)
    return client.disconnect(nowait=nowait, update_callback=update_callback)


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
                    "client_status": None,
                    "wireguard_probe": False,
                }
            )
        )
    return result


@stopwatch
def inspect_connection(connection_name: str) -> GefyraConnectionItem:
    connections = list_connections()
    if connections:
        result = next(
            (conn for conn in connections if conn.name == connection_name),
            None,
        )
    else:
        result = None
    config = ClientConfiguration(connection_name=connection_name)
    try:
        cargo_container = config.DOCKER.containers.get(config.CARGO_CONTAINER_NAME)
        cargo_status = cargo_container.status
    except docker.errors.NotFound:
        cargo_status = "not found"
    try:
        client = get_client(config.CLIENT_ID, connection_name=config.CONNECTION_NAME)
        client_state = client._state.lower()
    except (GefyraClientNotFound, KeyError):
        client_state = "not found"

    wireguard_probe_successful = False
    if client_state == "active" and cargo_status == "running":
        config.CARGO_PROBE_TIMEOUT = 1
        try:
            probe_wireguard_connection(config)
            wireguard_probe_successful = True
        except GefyraConnectionError:
            wireguard_probe_successful = False
    return GefyraConnectionItem(
        name=connection_name,
        client_status=client_state,
        status=cargo_status,
        created=result.created if result else None,
        version=result.version if result else None,
        wireguard_probe=wireguard_probe_successful,
    )


@stopwatch
def remove_connection(connection_name: str, force: bool = False) -> bool:
    import docker

    config = ClientConfiguration(connection_name=connection_name)
    try:
        client = get_client(config.CLIENT_ID, connection_name=connection_name)
        client.deactivate_connection()
        client.wait_for_state(GefyraClientState.WAITING, timeout=60)
    except Exception as e:  # noqa E722
        logger.debug(e)
        pass
    try:
        cargo_container = config.DOCKER.containers.get(
            f"{config.CARGO_CONTAINER_NAME}",
        )
        cargo_container.remove(force=True)
    except docker.errors.NotFound as e:
        logger.debug(e)
        pass
    try:
        handle_remove_network(config)
    except docker.errors.NotFound as e:
        logger.debug(e)
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
