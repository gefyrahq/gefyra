import logging
import pytest
from pytest_kubernetes.providers import AClusterManager


logger = logging.getLogger()

def test_handle_crds_errors(k3d: AClusterManager):
    import kubernetes
    kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
    from gefyra.handler.startup import handle_crds

    handle_crds(logger)
    handle_crds(logger)

