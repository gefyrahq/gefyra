import logging
import os
import sys
from operator.utils import decode_secret

import kubernetes as k8s

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

core_api = k8s.client.CoreV1Api()
NAMESPACE = os.getenv("GEFYRA_NAMESPACE", "gefyra")


def get_cargo_connection_data():
    cargo_connection_secret = core_api.read_namespaced_secret(
        name="gefyra-cargo-connection", namespace=NAMESPACE
    )
    return decode_secret(cargo_connection_secret.data)


def deploy_cargo_container():
    # - build Dockerfile
    # - run Dockerfile
    pass


def bridge():
    # - get cargo connection secret
    # - deploy cargo container
    # - deploy app container
    # - create ireq
    # cargo_connection_data = get_cargo_connection_data()
    pass
