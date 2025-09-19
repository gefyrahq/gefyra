import pytest

from pytest_kubernetes.providers import AClusterManager

from tests.conftest import purge_gefyra_objects
from tests.e2e.base import GefyraTestCase


LOCAL_CONTAINER_NAME = "gefyra-new-backend"


@pytest.mark.parametrize("operator", ["operator_no_sa", "operator_with_sa"])
@pytest.fixture(scope="class", autouse=True)
def workloads_for_bridgetests(operator):
    operator.apply("tests/fixtures/nginx_exposed.yaml")
    yield
    operator.kubectl(
        ["delete", "-f", "tests/fixtures/nginx_exposed.yaml"], as_dict=False
    )
    try:
        operator.kubectl(["delete", "deploy", "nginx-deployment-gefyra"], as_dict=False)
    except RuntimeError:
        # if this has never been run from a test
        pass


@pytest.fixture(scope="class", autouse=True)
def clear_gefyra_clients(operator):
    yield
    purge_gefyra_objects(operator)


class TestGefyraBridge(GefyraTestCase):
    provider = "k3d"

    def test_bridge(self, operator: AClusterManager, tmp_path, demo_backend_image):
        self.cmd(operator.kubeconfig, "client", ["create", "--client-id", "client-a"])

        operator.wait(
            "gefyraclients.gefyra.dev/client-a",
            "jsonpath=.state=WAITING",
            namespace="gefyra",
            timeout=60,
        )
        client_file_path = tmp_path / "client-a.json"
        self.cmd(
            operator.kubeconfig,
            "client",
            ["config", "-o", client_file_path, "client-a", "--local"],
        )

        self.cmd(
            operator.kubeconfig,
            "connection",
            ["connect", "-f", client_file_path, "--connection-name", "pytest-gefyra"],
        )
        operator.wait(
            "gefyraclients.gefyra.dev/client-a",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )

        self.cmd(
            operator.kubeconfig,
            "run",
            [
                "-i",
                demo_backend_image,
                "-n",
                "default",
                "--connection-name",
                "pytest-gefyra",
                "--expose",
                "127.0.0.1:8000:8000",
                "--rm",
                "--name",
                LOCAL_CONTAINER_NAME,
                "--command",
                "python3 local.py",
            ],
        )

        self.assert_get_contains("http://localhost:8000", "Hello from Gefyra.")

        self.assert_get_contains("http://localhost:8080", "Welcome to nginx!")

        self.cmd(
            operator.kubeconfig,
            "mount",
            [
                "create",
                "--target",
                "deploy/nginx-deployment/nginx",
                "--wait",
                "--connection-name",
                "pytest-gefyra",
            ],
        )
        operator.wait(
            "gefyrabridgemounts.gefyra.dev/nginx-deployment-gefyra",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )
        operator.wait(
            "deployment/nginx-deployment-gefyra",
            "jsonpath=.spec.template.spec.containers[0].image=nginx:1.14.2",
            namespace="default",
            timeout=60,
        )

        self.assert_get_contains("http://localhost:8080", "Welcome to nginx!")

        # TODO maybe check the new deployment?

        self.cmd(
            operator.kubeconfig,
            "bridge",
            [
                "--name",
                LOCAL_CONTAINER_NAME,
                "--ports",
                "80:8000",
                "--match-header",
                "x-gefyra:peer",
                "--target",
                "nginx-deployment-gefyra",
                "--connection-name",
                "pytest-gefyra",
            ],
        )

        result = operator.kubectl(
            ["get", "gefyrabridges.gefyra.dev", "-n", "gefyra"],
            as_dict=True,
        )

        bridge_name = result["items"][0]["metadata"]["name"]

        operator.wait(
            f"gefyrabridges.gefyra.dev/{bridge_name}",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )

        self.assert_get_contains("http://localhost:8080", "Welcome to nginx!")

        self.assert_get_contains(
            "http://localhost:8080", "Hello from Gefyra.", headers={"x-gefyra": "peer"}
        )

    def test_image_deployment_patches(
        self, operator: AClusterManager, tmp_path, demo_backend_image
    ):
        """
        Test if a deployment image patch is detected and the bridge is updated accordingly.
        """
        client_file_path = tmp_path / "client-a.json"
        self.cmd(
            operator.kubeconfig,
            "client",
            ["config", "-o", client_file_path, "client-a", "--local"],
        )

        self.cmd(
            operator.kubeconfig,
            "connection",
            ["connect", "-f", client_file_path, "--connection-name", "pytest-gefyra"],
        )

        self.cmd(
            operator.kubeconfig,
            "run",
            [
                "-i",
                demo_backend_image,
                "-n",
                "default",
                "--connection-name",
                "pytest-gefyra",
                "--expose",
                "127.0.0.1:8000:8000",
                "--rm",
                "--name",
                LOCAL_CONTAINER_NAME,
                "--command",
                "python3 local.py",
            ],
        )

        operator.kubectl(
            [
                "patch",
                "deployment",
                "nginx-deployment",
                "-n",
                "default",
                "--patch",
                '\'{"spec":{"template":{"spec":{"containers":[{"name":"nginx","image":"nginx:latest"}]}}}}\'',
            ]
        )

        operator.wait(
            "deployment/nginx-deployment-gefyra",
            "jsonpath=.spec.template.spec.containers[0].image=nginx:latest",
            namespace="default",
            timeout=60,
        )

        # RESTORING state usually lasts just very briefly, so we wait for PREPARING state
        operator.wait(
            "gefyrabridgemounts.gefyra.dev/nginx-deployment-gefyra",
            "jsonpath=.state=PREPARING",
            namespace="gefyra",
            timeout=60,
        )

        operator.wait(
            "gefyrabridgemounts.gefyra.dev/nginx-deployment-gefyra",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )

        self.assert_get_contains("http://localhost:8080", "Welcome to nginx!")

        self.assert_get_contains(
            "http://localhost:8080", "Hello from Gefyra.", headers={"x-gefyra": "peer"}
        )

    def test_rollout_bridge_mount_reconciles(
        self, operator: AClusterManager, tmp_path, demo_backend_image
    ):
        """
        Test if a deployment rollout is detected and the bridge is updated accordingly.
        """
        client_file_path = tmp_path / "client-a.json"
        self.cmd(
            operator.kubeconfig,
            "client",
            ["config", "-o", client_file_path, "client-a", "--local"],
        )

        self.cmd(
            operator.kubeconfig,
            "connection",
            ["connect", "-f", client_file_path, "--connection-name", "pytest-gefyra"],
        )

        self.cmd(
            operator.kubeconfig,
            "run",
            [
                "-i",
                demo_backend_image,
                "-n",
                "default",
                "--connection-name",
                "pytest-gefyra",
                "--expose",
                "127.0.0.1:8000:8000",
                "--rm",
                "--name",
                LOCAL_CONTAINER_NAME,
                "--command",
                "python3 local.py",
            ],
        )

        operator.kubectl(
            [
                "rollout",
                "restart",
                "deployment/nginx-deployment",
            ]
        )

        operator.wait(
            "gefyrabridgemounts.gefyra.dev/nginx-deployment-gefyra",
            "jsonpath=.state=RESTORING",
            namespace="gefyra",
            timeout=60,
        )

        operator.wait(
            "gefyrabridgemounts.gefyra.dev/nginx-deployment-gefyra",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )

        self.assert_get_contains("http://localhost:8080", "Welcome to nginx!")

        self.assert_get_contains(
            "http://localhost:8080", "Hello from Gefyra.", headers={"x-gefyra": "peer"}
        )
