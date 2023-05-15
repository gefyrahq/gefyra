import logging

from gefyra.configuration import default_configuration, ClientConfiguration

logger = logging.getLogger("gefyra")


def probe_docker(config: ClientConfiguration = default_configuration):
    logger.info("Checking Docker client.")
    try:
        config.DOCKER.containers.list()
        logger.info("Docker client: Ok")
        logger.info("Checking availability of Gefyra Cargo image...")
        config.DOCKER.images.pull("quay.io/gefyra/cargo:latest")
        logger.info("Gefyra Cargo: Available")
    except Exception:
        logger.error("Docker does not seem to be not working for Gefyra")
        return False
    else:
        logger.info("Docker: Ok")
        return True


def probe_kubernetes(config: ClientConfiguration = default_configuration):
    logger.info("Checking Kubernetes connection.")
    try:
        config.K8S_CORE_API.list_namespace()
    except Exception:
        logger.error(
            "Kubernetes is not connected to a cluster or does not seem to be working for Gefyra"
        )
        return False
    else:
        logger.info("Kubernetes: Ok")
        return True
