from os import path
import os
import platform
import struct
import socket
import sys
import logging
from typing import Optional, Union

from pathlib import Path


from gefyra.local import (
    CONNECTION_NAME_LABEL,
    CARGO_ENDPOINT_LABEL,
    ACTIVE_KUBECONFIG_LABEL,
    CLIENT_ID_LABEL,
)

console = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(levelname)s] %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger("gefyra")
logger.addHandler(console)

__VERSION__ = "2.0.0-alpha"
USER_HOME = os.path.expanduser("~")


def fix_pywin32_in_frozen_build() -> None:  # pragma: no cover
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
        connection_name: str = None,
        cargo_endpoint_host: str = None,
        cargo_endpoint_port: str = "31820",
        cargo_container_name: str = None,
        registry_url: str = None,
        operator_image_url: str = None,
        stowaway_image_url: str = None,
        carrier_image_url: str = None,
        cargo_image_url: str = None,
        kube_config_file: str = None,
        kube_context: str = None,
        wireguard_mtu: str = "1340",
        client_id: str = None,
        gefyra_config_root: Optional[Union[str, Path]] = None,
    ):
        if sys.platform == "win32":  # pragma: no cover
            fix_pywin32_in_frozen_build()
        self.NAMESPACE = "gefyra"  # another namespace is currently not supported
        self._kube_config_path = None
        self._kube_context = None
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

        self.cargo_endpoint_port = cargo_endpoint_port

        self.CARGO_CONTAINER_NAME = cargo_container_name or "gefyra-cargo"
        self.STOWAWAY_IP = "192.168.99.1"
        self.NETWORK_NAME = network_name or "gefyra"
        self.CONNECTION_NAME = connection_name or "default"
        self.BRIDGE_TIMEOUT = 60  # in seconds
        self.CONNECTION_TIMEOUT = 10  # in seconds
        self.CARGO_PROBE_TIMEOUT = 10  # in seconds
        self.CONTAINER_RUN_TIMEOUT = 10  # in seconds
        self.CLIENT_ID = client_id
        containers = self.DOCKER.containers.list(
            all=True,
            filters={"label": f"{CONNECTION_NAME_LABEL}={self.CONNECTION_NAME}"},
        )
        if containers:
            cargo_container = containers[0]
            self.CARGO_ENDPOINT = cargo_container.labels.get(CARGO_ENDPOINT_LABEL)
            self.KUBE_CONFIG_FILE = cargo_container.labels.get(ACTIVE_KUBECONFIG_LABEL)
            self.CLIENT_ID = cargo_container.labels.get(CLIENT_ID_LABEL)
            self.NETWORK_NAME = (  # TODO set base network name
                f"{self.NETWORK_NAME}-{self.CONNECTION_NAME}"
            )
            self.CARGO_CONTAINER_NAME = cargo_container.name

        if cargo_endpoint_host:
            self.CARGO_ENDPOINT = f"{cargo_endpoint_host}:{self.cargo_endpoint_port}"

        if kube_config_file:
            self.KUBE_CONFIG_FILE = kube_config_file

        if kube_context:
            self.KUBE_CONTEXT = kube_context

        self.WIREGUARD_MTU = wireguard_mtu
        if not gefyra_config_root:
            self.GEFYRA_LOCATION = Path.home().joinpath(".gefyra")
        else:
            self.GEFYRA_LOCATION = Path(gefyra_config_root)

    @property
    def CARGO_ENDPOINT(self):
        if hasattr(self, "_cargo_endpoint") and self._cargo_endpoint:
            return self._cargo_endpoint
        else:
            if (
                platform.system().lower() == "linux"
                and "microsoft" not in platform.release().lower()
            ):
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
                return f"{_ip}:{self.cargo_endpoint_port}"
            else:
                try:
                    _ip_output = self.DOCKER.containers.run(
                        "alpine", "getent hosts host.docker.internal", remove=True
                    )
                    _ip = _ip_output.decode("utf-8").split(" ")[0]
                    return f"{_ip}:{self.cargo_endpoint_port}"
                except Exception as e:
                    logger.error("Could not create a valid configuration: " + str(e))

    @CARGO_ENDPOINT.setter
    def CARGO_ENDPOINT(self, value):
        self._cargo_endpoint = value

    @property
    def KUBE_CONTEXT(self):
        if not self._kube_context:
            from kubernetes.config.kube_config import list_kube_config_contexts
            from kubernetes.config.config_exception import ConfigException

            try:
                _, active_context = list_kube_config_contexts(
                    config_file=self.KUBE_CONFIG_FILE
                )
                self.KUBE_CONTEXT = active_context.get("name", None)
            except ConfigException:
                logger.error("Could not read active 'kubeconfig' context.")
                self.KUBE_CONTEXT = None
        return self._kube_context

    @KUBE_CONTEXT.setter
    def KUBE_CONTEXT(self, context):
        self._kube_context = context

    @property
    def KUBE_CONFIG_FILE(self):
        if not self._kube_config_path:
            from kubernetes.config.kube_config import KUBE_CONFIG_DEFAULT_LOCATION

            self.KUBE_CONFIG_FILE = KUBE_CONFIG_DEFAULT_LOCATION
        return self._kube_config_path

    @KUBE_CONFIG_FILE.setter
    def KUBE_CONFIG_FILE(self, kube_config_path):
        if not path.isfile(path.expanduser(kube_config_path)):
            raise RuntimeError(f"KUBE_CONFIG_FILE {kube_config_path} not found.")
        self._kube_config_path = kube_config_path

    def _init_docker(self):
        import docker
        from docker.context import ContextAPI

        try:
            ctx = ContextAPI.get_context()
            if ctx.name != "default":
                endpoint = ctx.endpoints["docker"]["Host"]
                self.DOCKER = docker.DockerClient(base_url=endpoint)
                logger.debug(f"Docker Context: {ctx.name}")
            else:
                self.DOCKER = docker.from_env()
        except docker.errors.DockerException as de:
            logger.fatal(f"Docker init error: {de}")
            raise RuntimeError("Docker init error. Docker host not running?") from None

    def _init_kubeapi(self):
        from kubernetes.client import (
            CoreV1Api,
            RbacAuthorizationV1Api,
            AppsV1Api,
            CustomObjectsApi,
        )
        from kubernetes.config import load_kube_config

        load_kube_config(self.KUBE_CONFIG_FILE, context=self.KUBE_CONTEXT)
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

    def get_kubernetes_api_url(self) -> str:
        return self.K8S_CORE_API.api_client.configuration.host


def get_gefyra_config_location() -> str:
    """
    It creates a directory for the client config if it doesn't
    already exist, and returns the path to that directory

    :param config: ClientConfiguration
    :type config: ClientConfiguration
    :return: The path to the directory where the files will be stored.
    """
    config = ClientConfiguration()
    config_dir = config.GEFYRA_LOCATION
    config_dir.mkdir(parents=True, exist_ok=True)
    return str(config_dir)
