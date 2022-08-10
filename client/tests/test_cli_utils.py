import os
from unittest import mock
from unittest.mock import patch

import yaml

from gefyra.local.utils import get_connection_from_kubeconfig


@patch("kubernetes.config.kube_config.KUBE_CONFIG_DEFAULT_LOCATION", "/tmp/kube.yaml")
def test_get_connection_from_kubeconfig_no_connection():
    endpoint = get_connection_from_kubeconfig()
    assert endpoint is None


@patch("kubernetes.config.kube_config.KUBE_CONFIG_DEFAULT_LOCATION", "/tmp/kube.yaml")
def test_get_connection_from_kubeconfig_connection():
    data = {
        "current-context": "fake",
        "contexts": [
            {
                "name": "fake",
                "gefyra": "127.0.0.1:8090",
            },
        ],
    }
    f = open("/tmp/kube.yaml", "w")
    yaml.dump(data, f)
    f.close()
    try:
        endpoint = get_connection_from_kubeconfig()
        assert endpoint == "127.0.0.1:8090"
    except AssertionError:
        os.remove(f.name)
        raise
    else:
        os.remove(f.name)


@patch("kubernetes.config.kube_config.KUBE_CONFIG_DEFAULT_LOCATION", "/tmp/kube1.yaml")
def test_get_connection_from_kubeconfig_no_file():
    endpoint = get_connection_from_kubeconfig()
    assert endpoint is None

