import logging
import os

import kubernetes as k8s

logger = logging.getLogger("gefyra")

try:
    k8s.config.load_incluster_config()
    logger.info("Loaded in-cluster config")
except k8s.config.ConfigException:
    # if the operator is executed locally load the current KUBECONFIG
    k8s.config.load_kube_config()
    logger.info("Loaded KUBECONFIG config")

# register all Kopf handler
mode = os.getenv("OP_MODE", default="Operator").lower()
if mode == "operator":
    logger.info("Gefyra Operator startup")
    from gefyra.handler.configure_operator import *  # noqa
    from gefyra.handler.startup import *  # noqa
    from gefyra.handler.clients import *  # noqa
    from gefyra.handler.bridges import *  # noqa
elif mode == "webhook":
    logger.info("Gefyra Operator webhook startup")
    import gefyra.handler.configure_webhook  # noqa
