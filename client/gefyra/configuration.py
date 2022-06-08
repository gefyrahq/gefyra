import struct
import socket
import sys
import logging

console = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(levelname)s] %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger("gefyra")
logger.addHandler(console)

__VERSION__ = "0.8.1"


def fix_pywin32_in_frozen_build() -> None:
    import os
    import site

    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return

    site.addsitedir(sys.path[0])
    customsite = os.path.join(sys.path[0], "lib")
    site.addsitedir(customsite)

    # sys.path has been extended; use final
    # path to locate dll folder and add it to path
    path = sys.path[-1]
    path = path.replace("Pythonwin", "pywin32_system32")
    os.environ["PATH"] += ";" + path

    # import pythoncom module
    import importlib
    import importlib.machinery

    for name in ["pythoncom", "pywintypes"]:
        filename = os.path.join(path, name + "39.dll")
        loader = importlib.machinery.ExtensionFileLoader(name, filename)
        spec = importlib.machinery.ModuleSpec(name=name, loader=loader, origin=filename)
        importlib._bootstrap._load(spec)  # type: ignore


class ClientConfiguration(object):
    def __init__(
        self,
        docker_client=None,
        network_name: str = None,
        cargo_endpoint: str = None,
        cargo_container_name: str = None,
        registry_url: str = None,
        operator_image_url: str = None,
        stowaway_image_url: str = None,
        carrier_image_url: str = None,
        cargo_image_url: str = None,
        kube_config_file: str = None,
    ):
        if sys.platform == "win32":
            fix_pywin32_in_frozen_build()
        self.NAMESPACE = "gefyra"  # another namespace is currently not supported
        self.REGISTRY_URL = (
            registry_url.rstrip("/") if registry_url else "quay.io/gefyra"
        )
        if registry_url:
            logger.debug(
                f"Using registry prefix (other than default): {self.REGISTRY_URL}"
            )
        self.OPERATOR_IMAGE = (
            operator_image_url or f"{self.REGISTRY_URL}/operator:{__VERSION__}"
        )
        if operator_image_url:
            logger.debug(
                f"Using Operator image (other than default): {operator_image_url}"
            )
        self.STOWAWAY_IMAGE = (
            stowaway_image_url or f"{self.REGISTRY_URL}/stowaway:{__VERSION__}"
        )
        if stowaway_image_url:
            logger.debug(
                f"Using Stowaway image (other than default): {stowaway_image_url}"
            )
        self.CARRIER_IMAGE = (
            carrier_image_url or f"{self.REGISTRY_URL}/carrier:{__VERSION__}"
        )
        if carrier_image_url:
            logger.debug(
                f"Using Carrier image (other than default): {carrier_image_url}"
            )
        self.CARGO_IMAGE = cargo_image_url or f"{self.REGISTRY_URL}/cargo:{__VERSION__}"
        if cargo_image_url:
            logger.debug(f"Using Cargo image (other than default): {cargo_image_url}")
        if docker_client:
            self.DOCKER = docker_client
        if cargo_endpoint:
            if len(cargo_endpoint.split(":")) != 2:
                raise Exception("Please provide the endpoint in the form <ip:port>")
            self.CARGO_ENDPOINT = cargo_endpoint
        else:
            logger.info(
                "There was no --endpoint argument provided. Connecting to a local Kubernetes node."
            )
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
        self.CARGO_PROBE_TIMEOUT = 10  # in seconds
        self.CONTAINER_RUN_TIMEOUT = 10  # in seconds
        self.KUBE_CONFIG_FILE = kube_config_file

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

        if self.KUBE_CONFIG_FILE:
            load_kube_config(self.KUBE_CONFIG_FILE)
        else:
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
