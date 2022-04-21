import struct
import socket
import sys
import logging

console = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(levelname)s] %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger("gefyra")
logger.addHandler(console)

__VERSION__ = "0.6.16"


class ClientConfiguration(object):
    def __init__(
        self,
        docker_client=None,
        network_name: str = None,
        cargo_endpoint: str = None,
        cargo_container_name: str = None,
    ):
        self.NAMESPACE = "gefyra"  # another namespace is currently not supported
        if docker_client:
            self.DOCKER = docker_client
        if cargo_endpoint:
            self.CARGO_ENDPOINT = cargo_endpoint
        else:
            if sys.platform in ["darwin", "win32"]:
                # docker for mac/win publishes ports on a special internal ip
                try:
                    _ip_output = self.DOCKER.containers.run(
                        "alpine", "getent hosts host.docker.internal", remove=True
                    )
                    _ip = _ip_output.decode("utf-8").split(" ")[0]
                    self.CARGO_ENDPOINT = f"{_ip}:31820"
                except Exception as e:
                    logger.error("Could not create a valid configuration: " + str(e))
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

    def _init_docker(self):
        import docker

        try:
            self.DOCKER = docker.from_env()
        except docker.errors.DockerException as de:
            logger.fatal(f"Docker init error: {de}")
            raise docker.errors.DockerException(
                "Docker init error. Docker host not running?"
            )

    def _init_kubeapi(self):
        from kubernetes.client import (
            CoreV1Api,
            RbacAuthorizationV1Api,
            AppsV1Api,
            CustomObjectsApi,
        )
        from kubernetes.config import load_kube_config

        load_kube_config()
        self.K8S_CORE_API = CoreV1Api()
        self.K8S_RBAC_API = RbacAuthorizationV1Api()
        self.K8S_APP_API = AppsV1Api()
        self.K8S_CUSTOM_OBJECT_API = CustomObjectsApi()

    def __getattr__(self, item):
        if item in [
            "K8S_CORE_API",
            "K8S_RBAC_API",
            "K8S_APP_API",
            "K8S_CUSTOM_OBJECT_API",
        ]:
            try:
                return self.__getattribute__(item)
            except AttributeError:
                self._init_kubeapi()
        if item == "DOCKER":
            try:
                return self.__getattribute__(item)
            except AttributeError:
                self._init_docker()

        return self.__getattribute__(item)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k.isupper()}

    def __str__(self):
        return str(self.to_dict())


default_configuration = ClientConfiguration()
