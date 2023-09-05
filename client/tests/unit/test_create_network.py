import pytest
from docker.errors import APIError

from gefyra.configuration import ClientConfiguration
from gefyra.local.networking import get_or_create_gefyra_network


def test_cycle_gefyra_network():
    config = ClientConfiguration()
    gefyra_network = get_or_create_gefyra_network(config)
    gefyra_network.remove()


def test_gefyra_network_create_failed(monkeypatch):
    def _raise_apierror_for_docker_network_create(*args, **kwargs):
        raise APIError("Something with pool overlap")

    monkeypatch.setattr(
        "docker.api.network.NetworkApiMixin.create_network",
        _raise_apierror_for_docker_network_create,
    )
    config = ClientConfiguration()
    with pytest.raises(APIError):
        get_or_create_gefyra_network(config)
