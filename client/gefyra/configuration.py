import fcntl
import struct
import socket
import sys

import docker
import kubernetes as k8s
from docker import DockerClient

k8s.config.load_kube_config()


class ClientConfiguration:
    def __init__(
        self,
        # namespace: str = None,
        docker_client: DockerClient = None,
        network_name: str = None,
        cargo_endpoint: str = None,
        cargo_container_name: str = None,
    ):
        self.NAMESPACE = "gefyra"  # another namespace is currently not supported
        self.DOCKER = docker_client or docker.from_env()
        if cargo_endpoint:
            self.CARGO_ENDPOINT = cargo_endpoint
        else:
            # todo add windows platform
            if sys.platform == "darwin":
                # docker for mac publishes ports on localhost
                hostname = socket.gethostname()
                _ip = socket.gethostbyname(hostname)
                self.CARGO_ENDPOINT = f"{_ip}:31820"
            else:
                # get linux docker0 network address
                _soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                _ip = socket.inet_ntoa(
                    fcntl.ioctl(
                        _soc.fileno(),
                        0x8915,
                        struct.pack("256s", "docker0".encode("utf-8")[:15]),
                    )[20:24]
                )
                self.CARGO_ENDPOINT = f"{_ip}:31820"
        self.CARGO_CONTAINER_NAME = cargo_container_name or "gefyra-cargo"
        self.STOWAWAY_IP = "192.168.99.1"
        self.NETWORK_NAME = network_name or "gefyra"
        self.BRIDGE_TIMEOUT = 60  # in seconds
        self.K8S_CORE_API = k8s.client.CoreV1Api()
        self.K8S_RBAC_API = k8s.client.RbacAuthorizationV1Api()
        self.K8S_APP_API = k8s.client.AppsV1Api()
        self.K8S_CUSTOM_OBJECT_API = k8s.client.CustomObjectsApi()

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k.isupper()}

    def __str__(self):
        return str(self.to_dict())


default_configuration = ClientConfiguration()
