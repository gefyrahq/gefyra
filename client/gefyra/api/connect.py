import logging

from gefyra.configuration import default_configuration
from gefyra.local.cargo import probe_wireguard_connection


from . import down


logger = logging.getLogger(__name__)


def connect(config=default_configuration) -> bool:
    # 1. get or create a dedicated gefyra network with suffix (from connection name)
    # 2. try activate the GeyfraClient in the cluster by submitting the subnet (see: operator/tests/e2e/test_connect_clients.py)
    # -> feature to add to the GefyraClient type (see: client/gefyra/types.py)
    # 3. get the wireguard config from the GefyraClient
    # 4. Deploy Cargo with the wireguard config (see code from here: operator/tests/e2e/utils.py)


    #
    # Confirm the wireguard connection working
    #
    try:
        probe_wireguard_connection(config)
    except Exception as e:
        logger.error(e)
        down(config)
        return False
    return True
