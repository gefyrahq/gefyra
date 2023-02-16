import logging
import pytest
from pytest_kubernetes.providers import AClusterManager

from kopf.testing import KopfRunner

@pytest.fixture
def operator(k8s: AClusterManager):
    k8s.create()
    k8s.kubectl(["create", "ns", "gefyra"])
    operator = KopfRunner(["run", "-A", "--dev", "main.py"])
    operator.__enter__()
    kopf_logger = logging.getLogger("kopf")
    kopf_logger.setLevel(logging.CRITICAL)
    beiboot_logger = logging.getLogger("gefyra")
    beiboot_logger.setLevel(logging.CRITICAL)
    yield (operator, k8s)
    operator.__exit__(None, None, None)
    k8s.delete()
    
    