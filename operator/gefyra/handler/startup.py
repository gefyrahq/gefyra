import kopf
import kubernetes as k8s

from gefyra.resources.crds import (
    create_gefyraclient_definition,
    create_gefyrabridge_definition,
)
from gefyra.resources.events import create_operator_ready_event
from gefyra.connection.factory import (
    ConnectionProviderType,
    connection_provider_factory,
)

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
extension_api = k8s.client.ApiextensionsV1Api()
events = k8s.client.EventsV1Api()


def handle_crds(logger) -> None:
    ireqs = create_gefyrabridge_definition()
    try:
        extension_api.create_custom_resource_definition(body=ireqs)
        logger.info("Gefyra CRD gefyrabridge created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.warning(
                "Gefyra CRD gefyrabridge already available but might be outdated. "
                "Please remove it manually if you encounter issues."
            )
        else:
            raise e
    gclients = create_gefyraclient_definition()
    try:
        extension_api.create_custom_resource_definition(body=gclients)
        logger.info("Gefyra CRD gefyraclient created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.warning(
                "Gefyra CRD gefyraclient already available but might "
                "be outdated. Please remove it manually if you encounter issues."
            )
        else:
            raise e


@kopf.on.startup()
async def check_gefyra_components(logger, **kwargs) -> None:
    """
    Checks all required components of Gefyra in the current version.
    This handler installs components if they are
    not already available with the matching configuration.
    """
    from gefyra.configuration import configuration

    logger.info(
        f"Ensuring Gefyra components with the following configuration: {configuration}"
    )
    # handle Gefyra CRDs and Permissions
    handle_crds(logger)


@kopf.on.startup()
async def start_connection_providers(logger, retry, **kwargs) -> None:
    """
    Starts all connection providers that are configured in the current version
    """
    from gefyra.configuration import configuration

    logger.info("Starting up connection providers")
    not_ready_providers = []
    for gefyra_connector in ConnectionProviderType:
        provider = connection_provider_factory.get(
            gefyra_connector,
            configuration,
            logger,
        )
        if not provider.installed():
            provider.install()
            logger.info(f"Installing connection provider {gefyra_connector.name}")
        if provider.installed() and not provider.ready():
            not_ready_providers.append(gefyra_connector)

    if not_ready_providers:
        if retry > configuration.CONNECTION_PROVIDER_STARTUP_TIMEOUT:
            info = "No pod found"
            pod = provider._get_stowaway_pod()
            if pod:
                info = (
                    f"Pod {pod.metadata.name} in namespace {pod.metadata.namespace} is in state "
                    f"{pod.status.phase}, {pod.status.message}"
                )

            raise kopf.PermanentError(
                f"Connection provider(s) {not_ready_providers} could not be started. Podinfo: {info}"
            )
        else:
            raise kopf.TemporaryError(
                (
                    f"Connection provider(s) {gefyra_connector.name} is not ready yet "
                    f"(retry {retry}/"
                    f"{configuration.CONNECTION_PROVIDER_STARTUP_TIMEOUT})))"
                ),
                delay=1,
            )

    def _write_startup_task():
        try:
            events.create_namespaced_event(
                body=create_operator_ready_event(configuration.NAMESPACE),
                namespace=configuration.NAMESPACE,
            )
        except k8s.client.exceptions.ApiException as e:
            if e.status != 409:
                logger.error("Could not create startup event: " + str(e))

    _write_startup_task()
    logger.info("Gefyra components installed/patched")
