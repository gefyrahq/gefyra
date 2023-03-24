import kopf
import kubernetes as k8s

from gefyra.resources.crds import (
    create_gefyraclient_definition,
    create_interceptrequest_definition,
)
from gefyra.resources.events import create_operator_ready_event
from gefyra.connection.factory import ProviderType, connection_provider_factory

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
extension_api = k8s.client.ApiextensionsV1Api()
events = k8s.client.EventsV1Api()


def handle_crds(logger) -> None:
    ireqs = create_interceptrequest_definition()
    try:
        extension_api.create_custom_resource_definition(body=ireqs)
        logger.info("Gefyra CRD InterceptRequest created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.warn(
                "Gefyra CRD InterceptRequest already available but might be outdated"
            )
        else:
            raise e
    gclients = create_gefyraclient_definition()
    try:
        extension_api.create_custom_resource_definition(body=gclients)
        logger.info("Gefyra CRD GefyraClients created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.warn(
                "Gefyra CRD InterceptRequest already available but might be outdated"
            )
        else:
            raise e


@kopf.on.startup()
async def check_gefyra_components(logger, **kwargs) -> None:
    """
    Checks all required components of Gefyra in the current version. This handler installs components if they are
    not already available with the matching configuration.
    """
    from gefyra.configuration import configuration


    logger.info(
        f"Ensuring Gefyra components with the following configuration: {configuration}"
    )
    # handle Gefyra CRDs and Permissions
    handle_crds(logger)


@kopf.on.startup()
async def start_connection_providers(logger, **kwargs) -> None:
    """
    Starts all connection providers that are configured in the current version
    """
    from gefyra.configuration import configuration

    for gefyra_connector in ProviderType:
        provider = connection_provider_factory.get(
            gefyra_connector,
            configuration,
            logger,
        )
        await provider.install()
        
        @kopf.subhandler(id=f"wait_connection-provider_{gefyra_connector.name}")
        async def start_connection_provider(retries, **kwargs):
            if retries > configuration.CONNECTION_PROVIDER_STARTUP_TIMEOUT / 2:
                raise kopf.PermanentError(f"Connection provider {gefyra_connector.name} could not be started")
            if provider.ready():
                logger.info(f"Connection provider {gefyra_connector.name} is ready")
            else:
                raise kopf.TemporaryError(f"Connection provider {gefyra_connector.name} is not ready yet", delay=2)

    def _write_startup_task():
        try:
            events.create_namespaced_event(
                body=create_operator_ready_event(configuration.NAMESPACE),
                namespace=configuration.NAMESPACE,
            )
        except k8s.client.exceptions.ApiException as e:
            logger.error("Could not create startup event: " + str(e))

    _write_startup_task()
    logger.info("Gefyra components installed/patched")
