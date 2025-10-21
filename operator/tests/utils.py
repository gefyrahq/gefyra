from datetime import datetime
from pathlib import Path
import subprocess
from time import sleep
import docker

# flake8: noqa
import io
import sys
import platform


def get_dockerfile():
    return io.BytesIO(
        """ 
FROM "cargo:pytest"

ARG ADDRESS
ARG MTU
ARG PRIVATE_KEY
ARG DNS
ARG PUBLIC_KEY
ARG ENDPOINT
ARG ALLOWED_IPS
ARG PRESHAREDKEY

RUN mkdir /config/
RUN touch /config/wg0.conf

RUN echo -e '[Interface] \\n\
Address = '"$ADDRESS"' \\n\
PrivateKey = '"$PRIVATE_KEY"' \\n\
DNS = '"$DNS"' \\n\
PreUp = sysctl -w net.ipv4.ip_forward=1 \\n\
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth1 -j MASQUERADE \\n\ 
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth1 -j MASQUERADE \\n\
\\n\
[Peer] \\n\
PublicKey = '"$PUBLIC_KEY"' \\n\
Endpoint = '"$ENDPOINT"' \\n\
PresharedKey = '"$PRESHAREDKEY"' \\n\
PersistentKeepalive = 21 \\n\
AllowedIPs = '"$ALLOWED_IPS" > /config/wg0.conf

RUN cat /config/wg0.conf
""".encode(
            "utf-8"
        )
    )


class GefyraDockerClient:
    def __init__(self, name: str) -> None:
        self.name = name
        self.docker = docker.from_env()
        docker_os = self._get_docker_info_by_name("OperatingSystem")
        docker_server_name = self._get_docker_info_by_name("Name")
        if (
            "docker desktop" in docker_os
            or "windows" in docker_os
            or "colima" in docker_server_name
        ):
            _ip_output = self.docker.containers.run(
                "alpine", "getent hosts host.docker.internal", remove=True
            )
            _ip = _ip_output.decode("utf-8").split(" ")[0]
        else:
            # get linux docker0 network address
            import fcntl
            import socket
            import struct

            _soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            _ip = socket.inet_ntoa(
                fcntl.ioctl(
                    _soc.fileno(),
                    0x8915,
                    struct.pack("256s", "docker0".encode("utf-8")[:15]),
                )[20:24]
            )
        self.endpoint = f"{_ip}:31820"

    def _get_docker_info_by_name(self, name):
        try:
            return self.docker.info()[name].lower()
        except Exception:
            return ""

    def connect(self, configs: dict):
        self.configs = configs
        wireguard_ip = self.configs["Interface.Address"]
        private_key = self.configs["Interface.PrivateKey"]
        dns = f"{self.configs['Interface.DNS']} demo.svc.cluster.local"
        public_key = self.configs["Peer.PublicKey"]
        # docker to work with ipv4 only
        allowed_ips = self.configs["Peer.AllowedIPs"].split(",")[0]
        presharedkey = self.configs["Peer.PresharedKey"]

        build_args = {
            "ADDRESS": wireguard_ip,
            "PRIVATE_KEY": private_key,
            "DNS": dns,
            "PUBLIC_KEY": public_key,
            "ENDPOINT": self.endpoint,
            "ALLOWED_IPS": allowed_ips,
            "PRESHAREDKEY": presharedkey,
        }

        tag = f"gefyra-client-cargo:{datetime.now().strftime('%Y%m%d%H%M%S')}"
        # check for Cargo updates

        # build this instance
        _Dockerfile = get_dockerfile()
        image, _ = self.docker.images.build(
            fileobj=_Dockerfile, rm=True, forcerm=True, buildargs=build_args, tag=tag
        )
        # we only have one tag
        image_name_and_tag = image.tags[0]
        # run image
        self.container = self.docker.containers.create(
            image_name_and_tag,
            detach=True,
            name=self.name,
            auto_remove=True,
            cap_add=["NET_ADMIN"],
            privileged=True,
            volumes=["/var/run/docker.sock:/var/run/docker.sock"],
        )
        self.container.start()
        _i = 10
        while _i > 0:
            try:
                r = self.container.exec_run("wg")
                if "transfer:" in r.output.decode("utf-8"):
                    break
            except Exception:
                pass
            _i -= 1
            sleep(1)
            continue

    def probe(self):
        cargo = self.container
        for _ in range(0, 20):
            _exit_code, _ = cargo.exec_run(f"timeout 1 ping -c 1 192.168.99.1")
            if _exit_code != 0:
                continue
            else:
                break
        else:
            raise RuntimeError("Failed to connect to wireguard client")

    def delete(self):
        if hasattr(self, "container"):
            self.container.stop()
            self.container = None
