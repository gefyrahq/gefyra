import logging

import kubernetes as k8s

logger = logging.getLogger("gefyra")
logger.info("Gefyra Operator startup")

try:
    k8s.config.load_incluster_config()
    logger.info("Loaded in-cluster config")
except k8s.config.ConfigException:
    # if the operator is executed locally load the current KUBECONFIG
    k8s.config.load_kube_config()
    logger.info("Loaded KUBECONFIG config")


# register all Kopf handler
from gefyra.handler import *  # noqa
