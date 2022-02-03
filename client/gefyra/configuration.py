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
        self.CARGO_ENDPOINT = cargo_endpoint or "172.17.0.1:31820"
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
