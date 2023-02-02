import logging
from dataclasses import dataclass
from enum import Enum

from gefyra.api import stopwatch
from gefyra.configuration import default_configuration, ClientConfiguration

logger = logging.getLogger(__name__)


@dataclass
class GefyraClusterStatus:
    # is a kubernetes cluster reachable
    connected: bool
    # is the operator running
    operator: bool
    operator_image: str
    # is stowaway running
    stowaway: bool
    stowaway_image: str
    # the gefyra namespace is available
    namespace: bool


@dataclass
class GefyraClientStatus:
    version: str
    # is cargo running
    cargo: bool
    cargo_image: str
    # is gefyra network available
    network: bool
    # is gefyra client connected with gefyra cluster
    connection: bool
    # amount of containers running in gefyra
    containers: int
    # amount of active bridges
    bridges: int
    # current kubeconfig file
    kubeconfig: str
    # current kubeconfig context
    context: str
    # wireguard endpoint
    cargo_endpoint: str


class StatusSummary(str, Enum):
    UP = "Gefyra is up and connected"
    DOWN = "Gefyra is not running"
    INCOMPLETE = "Gefyra is not running properly"


@dataclass
class GefyraStatus:
    summary: StatusSummary
    cluster: GefyraClusterStatus
    client: GefyraClientStatus


def _get_client_status(config: ClientConfiguration) -> GefyraClientStatus:
    from docker.errors import NotFound
    from gefyra.local import CARGO_ENDPOINT_LABEL, VERSION_LABEL

    # these are the default values
    _status = GefyraClientStatus(
        cargo=False,
        version="",
        cargo_image=config.CARGO_IMAGE,
        network=False,
        connection=False,
        containers=0,
        bridges=0,
        kubeconfig=config.KUBE_CONFIG_FILE,
        context=config.KUBE_CONTEXT,
        cargo_endpoint="",
    )
    try:
        logger.debug("Checking cargo container running")
        cargo_container = config.DOCKER.containers.get(config.CARGO_CONTAINER_NAME)
        if cargo_container.status == "running":
            _status.cargo = True
            _status.cargo_endpoint = cargo_container.attrs["Config"]["Labels"].get(
                CARGO_ENDPOINT_LABEL
            )
            _status.version = cargo_container.attrs["Config"]["Labels"].get(
                VERSION_LABEL
            )
            _status.cargo_image = cargo_container.image.tags[0]
    except NotFound:
        pass
    try:
        logger.debug("Checking gefyra network available")
        gefyra_net = config.DOCKER.networks.get(config.NETWORK_NAME)
        _status.network = True
        _status.containers = (
            len(gefyra_net.containers) - 1
            if _status.cargo is True
            else len(gefyra_net.containers)
        )
    except NotFound:
        return _status

    from gefyra.local.cargo import probe_wireguard_connection

    try:
        logger.debug("Probing wireguard connection")
        if _status.cargo:
            probe_wireguard_connection(config)
            _status.connection = True
    except RuntimeError:
        return _status

    from gefyra.local.bridge import get_all_interceptrequests

    logger.debug("Counting all active bridges")
    _status.bridges = len(get_all_interceptrequests(config))
    return _status


def _get_cluster_status(config: ClientConfiguration) -> GefyraClusterStatus:
    from kubernetes.client import ApiException
    from kubernetes.config import ConfigException
    from urllib3.exceptions import MaxRetryError

    # these are the default values
    _status = GefyraClusterStatus(
        connected=False,
        operator=False,
        operator_image="",
        stowaway=False,
        stowaway_image="",
        namespace=False,
    )
    # check if connected to the cluster
    try:
        logger.debug("Reading API resources from Kubernetes")
        config.K8S_CORE_API.get_api_resources(_request_timeout=(1, 5))
        _status.connected = True
    except (ApiException, ConfigException, MaxRetryError):
        return _status
    # check if gefyra namespace is available
    try:
        logger.debug("Reading gefyra namespace")
        config.K8S_CORE_API.read_namespace(
            name=config.NAMESPACE, _request_timeout=(1, 5)
        )
        _status.namespace = True
    except ApiException:
        return _status
    # check if the Gefyra operator is running and ready
    try:
        logger.debug("Checking operator deployment")
        operator_deploy = config.K8S_APP_API.read_namespaced_deployment(
            name="gefyra-operator", namespace=config.NAMESPACE, _request_timeout=(1, 5)
        )
        if (
            operator_deploy.status.ready_replicas
            and operator_deploy.status.ready_replicas >= 1
        ):
            _status.operator = True
            _status.operator_image = operator_deploy.spec.template.spec.containers[
                0
            ].image
    except ApiException:
        return _status

    # check if the Gefyra operator is running and ready
    try:
        logger.debug("Checking Stowaway deployment")
        stowaway_deploy = config.K8S_APP_API.read_namespaced_deployment(
            name="gefyra-stowaway", namespace=config.NAMESPACE, _request_timeout=(1, 5)
        )
        if (
            stowaway_deploy.status.ready_replicas
            and stowaway_deploy.status.ready_replicas >= 1
        ):
            _status.stowaway = True
            _status.stowaway_image = stowaway_deploy.spec.template.spec.containers[
                0
            ].image
    except ApiException:
        pass

    return _status


@stopwatch
def status(config=default_configuration) -> GefyraStatus:
    from gefyra.local.utils import set_kubeconfig_from_cargo

    # Check if kubeconfig is available through running Cargo
    config = set_kubeconfig_from_cargo(config)

    cluster = _get_cluster_status(config)
    client = _get_client_status(config)
    if client.connection:
        summary = StatusSummary.UP
    else:
        if client.cargo or (
            cluster.connected and cluster.operator and cluster.stowaway
        ):
            summary = StatusSummary.INCOMPLETE
        else:
            summary = StatusSummary.DOWN
    return GefyraStatus(cluster=cluster, client=client, summary=summary)
