from gefyra.configuration import ClientConfiguration
from gefyra.local.networking import _get_subnet


def test_subnet_negotiation():
    """This test assumes, that docker will reuse the same subnet, if it is free."""
    config = ClientConfiguration()
    temp_network = config.DOCKER.networks.create("gefyra-test-network")
    temp_subnet = temp_network.attrs["IPAM"]["Config"][0]["Subnet"]
    temp_network.remove()
    occupied_networks = [temp_subnet]
    subnet = _get_subnet(
        config=config,
        network_name="gefyra-test-network",
        occupied_networks=occupied_networks,
    )
    assert subnet != temp_subnet
