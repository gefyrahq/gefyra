import json
import logging
import time

from pytest_kubernetes.providers import AClusterManager
from tests.utils import GefyraDockerClient

logger = logging.getLogger(__name__)


def test_client_max_connection_age(
    operator: AClusterManager,
    gclient_a: GefyraDockerClient,
):
    """
    Test that verifies max_connection_age functionality:
    1. Install Gefyra in cluster with max_connection_age set to 5 seconds
    2. Create and connect a client
    3. Verify client is active
    4. Wait for max_connection_age to expire
    5. Verify client returns to waiting state
    """
    k3d = operator

    # Set max_connection_age to 5 seconds in the gefyra-stowaway-config configmap
    logger.info("Setting max_connection_age to 5 seconds in configmap")
    k3d.kubectl(
        [
            "patch",
            "configmap",
            "gefyra-stowaway-config",
            "-n",
            "gefyra",
            "--type=merge",
            "--patch='"
            + json.dumps({"data": {"DEFAULT_MAX_CONNECTION_AGE": "5"}})
            + "'",
        ]
    )

    # Restart the stowaway deployment to pick up the new config
    logger.info("Restarting stowaway deployment to pick up new config")
    k3d.kubectl(["rollout", "restart", "sts/gefyra-stowaway", "-n", "gefyra"])

    # Apply client configuration
    logger.info("Creating GefyraClient")
    k3d.apply("tests/fixtures/a_gefyra_client.yaml")

    # Wait for client to be in WAITING state
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=20,
    )

    # Connect the client by setting providerParameter
    logger.info("Connecting client by setting providerParameter")
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "patch",
            "gefyraclient",
            "client-a",
            "--type='merge'",
            "--patch='"
            + json.dumps({"providerParameter": {"subnet": "192.168.101.0/24"}})
            + "'",
        ]
    )

    # Wait for client to become ACTIVE
    logger.info("Waiting for client to become ACTIVE")
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=20,
    )

    # Verify client is active
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a["state"] == "ACTIVE"
    logger.info("Client is now ACTIVE")

    # Wait for max_connection_age to expire (5 seconds + buffer)
    logger.info("Waiting for max_connection_age to expire (7 seconds)")
    time.sleep(7)

    # Verify client has returned to WAITING state
    logger.info("Checking if client returned to WAITING state")
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=10,
    )

    # Final verification
    client_a_final = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a_final["state"] == "WAITING"
    logger.info(
        "Test passed: Client successfully returned to WAITING state after max_connection_age expired"
    )

    # Cleanup
    gclient_a.delete()
