import logging

from docker.errors import NotFound

from gefyra.configuration import ClientConfiguration
from gefyra.local.utils import (
    handle_docker_remove_container,
)
from gefyra.types import StowawayConfig

logger = logging.getLogger(__name__)


def remove_cargo_container(config: ClientConfiguration):
    try:
        handle_docker_remove_container(config, container_id=config.CARGO_CONTAINER_NAME)
    except NotFound:
        pass


def get_cargo_ip_from_netaddress(network_address: str) -> str:
    return ".".join(network_address.split(".")[:3]) + ".149"


def probe_wireguard_connection(config: ClientConfiguration):
    cargo = config.DOCKER.containers.get(f"{config.CARGO_CONTAINER_NAME}")
    for _attempt in range(0, config.CARGO_PROBE_TIMEOUT):
        _r = cargo.exec_run(f"timeout 1 ping -c 1 {config.STOWAWAY_IP}")
        if _r.exit_code != 0:
            continue
        else:
            break
    else:
        raise RuntimeError(
            "Gefyra could not successfully confirm the connection working."
        )


def create_wireguard_config(
    params: StowawayConfig, cargo_endpoint: str, mtu: str = "1340"
) -> str:
    return (
        "[Interface]\n"
        f"Address = {params.iaddress}\n"
        f"MTU = {mtu}\n"
        f"PrivateKey = {params.iprivatekey}\n"
        f"DNS = {params.idns}\n"
        "PreUp = sysctl -w net.ipv4.ip_forward=1\n"
        "PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth1 -j MASQUERADE\n"  # noqa E501
        "PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth1 -j MASQUERADE\n"  # noqa E501
        "[Peer]\n"
        f"PublicKey = {params.ppublickey}\n"
        f"Endpoint = {cargo_endpoint}\n"
        "PersistentKeepalive = 21\n"
        "AllowedIPs = 0.0.0.0/0\n"
    )
