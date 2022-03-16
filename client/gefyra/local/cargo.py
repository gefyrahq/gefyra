import io
import logging
import os
import tarfile

from docker.errors import NotFound
from docker.models.containers import Container

from gefyra.configuration import ClientConfiguration
from gefyra.local.utils import (
    build_cargo_image,
    handle_docker_create_container,
    handle_docker_remove_container,
)

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

    # build image
    image, build_logs = build_cargo_image(
        config,
        wireguard_ip=wireguard_ip,
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


def get_syncdown_config(config: ClientConfiguration) -> str:
    fh = io.BytesIO()
    cargo = config.DOCKER.containers.get(config.CARGO_CONTAINER_NAME)
    bits, stat = cargo.get_archive("/etc/syncdown.conf")
    for chunk in bits:
        fh.write(chunk)
    fh.seek(0)
    with tarfile.open(fileobj=fh) as tf:
        fconfig = tf.extractfile(stat["name"]).read().decode()
    return fconfig


def put_syncdown_config(config: ClientConfiguration, syncdown_configuration: str):
    cargo = config.DOCKER.containers.get(config.CARGO_CONTAINER_NAME)
    source_f = io.BytesIO()
    source_f.write(syncdown_configuration.encode())
    fh = io.BytesIO()
    with tarfile.open(fileobj=fh, mode="w") as tf:
        info = tarfile.TarInfo("syncdown.conf")
        info.size = source_f.tell()
        source_f.seek(0)
        tf.addfile(info, fileobj=source_f)
    fh.seek(0)
    cargo.put_archive("/etc/", fh)


def delete_syncdown_job(config: ClientConfiguration, bridge_name: str):
    configfile = get_syncdown_config(config)
    old_config = configfile.split("\n")
    new_config = []
    for line in old_config:
        if line.split(";")[0] != bridge_name:
            new_config.append(line)
    configfile = "\n".join(new_config)
    put_syncdown_config(config, configfile)


def add_syncdown_job(
    config: ClientConfiguration,
    bridge_name: str,
    to_container_name: str,
    from_pod: str,
    from_container: str,
    directory: str,
):
    configfile = get_syncdown_config(config)
    relative = directory.strip("/")
    target = os.path.split(directory)[0]
    # bridge name;container name;prefix;relative directory;target directory
    configfile = (
        configfile
        + f"\n{bridge_name};{to_container_name};{from_pod}/{from_container};{relative};{target}"
    )
    put_syncdown_config(config, configfile)
