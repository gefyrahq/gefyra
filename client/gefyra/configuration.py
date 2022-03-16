import struct
import socket
import sys

from docker import DockerClient, from_env
from kubernetes.client import (
    CoreV1Api,
    RbacAuthorizationV1Api,
    AppsV1Api,
    CustomObjectsApi,
)
from kubernetes.config import load_kube_config

__VERSION__ = "0.6.1"

load_kube_config()


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
        self.DOCKER = docker_client or from_env()
        if cargo_endpoint:
            self.CARGO_ENDPOINT = cargo_endpoint
        else:
            if sys.platform in ["darwin", "win32"]:
                # docker for mac/win publishes ports on localhost
                hostname = socket.gethostname()
                _ip = socket.gethostbyname(hostname)
                self.CARGO_ENDPOINT = f"{_ip}:31820"
            else:
                # get linux docker0 network address
                import fcntl

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
        self.K8S_CORE_API = CoreV1Api()
        self.K8S_RBAC_API = RbacAuthorizationV1Api()
        self.K8S_APP_API = AppsV1Api()
        self.K8S_CUSTOM_OBJECT_API = CustomObjectsApi()

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k.isupper()}

    def __str__(self):
        return str(self.to_dict())


default_configuration = ClientConfiguration()
