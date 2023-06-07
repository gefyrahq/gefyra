import logging

from docker.errors import NotFound
from docker.models.containers import Container

from gefyra.configuration import ClientConfiguration
from gefyra.local.utils import (
    build_cargo_image,
    handle_docker_create_container,
    handle_docker_remove_container,
)
from gefyra.types import StowawayConfig

logger = logging.getLogger(__name__)


def create_cargo_container(
    config: ClientConfiguration, cargo_connection_data: dict
) -> Container:
    wireguard_ip = f"{cargo_connection_data['Interface.Address']}"
    private_key = cargo_connection_data["Interface.PrivateKey"]
    dns = (
        f"{cargo_connection_data['Interface.DNS']} {config.NAMESPACE}.svc.cluster.local"
    )
    public_key = cargo_connection_data["Peer.PublicKey"]
    # docker to work with ipv4 only
    allowed_ips = cargo_connection_data["Peer.AllowedIPs"].split(",")[0]
    mtu = cargo_connection_data["MTU"]

    # build image
    image, build_logs = build_cargo_image(
        config,
        wireguard_ip=wireguard_ip,
        mtu=mtu,
        private_key=private_key,
        dns=dns,
        public_key=public_key,
        endpoint=config.CARGO_ENDPOINT,
        allowed_ips=allowed_ips,
    )
    # we only have one tag
    image_name_and_tag = image.tags[0]
    # run image
    container = handle_docker_create_container(
        config,
        image_name_and_tag,
        detach=True,
        name=config.CARGO_CONTAINER_NAME,
        auto_remove=True,
        cap_add=["NET_ADMIN"],
        privileged=True,
        volumes=["/var/run/docker.sock:/var/run/docker.sock"],
        pid_mode="host",
    )
    return container


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
            "Gefyra could not successfully confirm the Wireguard connection working."
            " Please make sure you are using the --endpoint argument for remote"
            f" clusters and that the Kubernetes NodePort {config.CARGO_ENDPOINT} can be"
            " reached from this machine. Please check your firewall settings, too. If"
            " you are running a local Minikube cluster, please use the 'gefyra up"
            " --minikube' flag."
        )


def create_wireguard_config(
    params: StowawayConfig, cargo_endpoint: str, mtu: str = "1340"
) -> str:
    return (
        "[Interface]"
        f"Address = {params.iaddress}"
        f"MTU = {mtu}"
        f"PrivateKey = {params.iprivatekey}"
        f"DNS = {params.idns}"
        "PreUp = sysctl -w net.ipv4.ip_forward=1"
        "PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth1 -j MASQUERADE"  # noqa E501
        "PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth1 -j MASQUERADE"  # noqa E501
        "[Peer]"
        f"PublicKey = {params.ppublickey}"
        f"Endpoint = {cargo_endpoint}"
        "PersistentKeepalive = 21"
        "AllowedIPs = 0.0.0.0/0"
    )
