import logging

from gefyra.api import stopwatch
from gefyra.configuration import ClientConfiguration
from gefyra.exceptions import ClientConfigurationError
from gefyra.types import (
    GefyraClientStatus,
    GefyraClusterStatus,
    GefyraStatus,
    StatusSummary,
)


logger = logging.getLogger(__name__)


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
        gefyra_net = config.DOCKER.networks.get(f"{config.NETWORK_NAME}")
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

    from gefyra.local.bridge import get_all_gefyrabridges

    logger.debug("Counting all active bridges")
    _status.bridges = len(get_all_gefyrabridges(config))
    return _status


def _get_cluster_status(config: ClientConfiguration) -> GefyraClusterStatus:
    from kubernetes.client import ApiException, V1Pod
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
        logger.debug("Checking Stowaway endpoint")
        stowaway_pod: V1Pod = config.K8S_CORE_API.read_namespaced_pod(
            name="gefyra-stowaway-0",
            namespace=config.NAMESPACE,
            _request_timeout=(1, 5),
        )
        if stowaway_pod.status.container_statuses[0].ready:
            _status.stowaway = True
            _status.stowaway_image = stowaway_pod.spec.containers[0].image
    except ApiException as e:
        logger.warning(e)
        pass

    return _status


@stopwatch
def status(connection_name: str = "") -> GefyraStatus:
    import urllib3

    # Check if kubeconfig is available through running Cargo
    config = ClientConfiguration(connection_name=connection_name)

    cluster = _get_cluster_status(config)
    try:
        client = _get_client_status(config)
    except urllib3.exceptions.MaxRetryError as e:
        raise ClientConfigurationError(
            f"Cannot reach cluster on {e.pool.host}:{e.pool.port}"
        )

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
