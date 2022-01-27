import logging
import subprocess

from gefyra.configuration import ClientConfiguration, default_configuration

logger = logging.getLogger(__name__)


def probe_nsenter():
    logger.debug("Probing: 'nsenter'")
    try:
        subprocess.check_call(
            ["nsenter", "-h"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )
    except Exception:
        logger.error("'nsenter' seems to be missing or is not working for Gefyra")
    else:
        logger.info("nsenter: Ok.")


def probe_docker(config: ClientConfiguration = default_configuration):
    logger.debug("Probing: Docker")
    try:
        config.DOCKER.containers.list()
        config.DOCKER.images.pull("quay.io/gefyra/cargo:latest")
    except Exception:
        logger.error("Docker does not seem to be not working for Gefyra")
    else:
        logger.info("Docker: Ok.")


def probe_kubernetes(config: ClientConfiguration = default_configuration):
    logger.debug("Probing: Kubernetes")
    try:
        config.K8S_CORE_API.list_namespace()
    except Exception:
        logger.error("Kubernetes does not seem to be working for Gefyra")
    else:
        logger.info("Kubernetes: Ok.")
