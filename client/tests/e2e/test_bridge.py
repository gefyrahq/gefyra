import pytest

from tests.e2e.base import GefyraTestCase

LOCAL_CONTAINER_NAME = "gefyra-new-backend"


@pytest.mark.usefixtures("operator")
@pytest.mark.usefixtures("tmp_path")
@pytest.mark.usefixtures("demo_backend_image")
class GefyraBridgeTest(GefyraTestCase):
    provider = "k3d"

    def test_bridge(self):
        self.cmd("client", ["create", "--client-id", "client-a"])

        self.operator.wait(
            "gefyraclients.gefyra.dev/client-a",
            "jsonpath=.state=WAITING",
            namespace="gefyra",
            timeout=60,
        )
        client_file_path = self.tmp_path / "client-a.json"
        self.cmd("client", ["config", "-o", client_file_path, "client-a", "--local"])

        self.cmd(
            "connection",
            ["connect", "-f", client_file_path, "--connection-name", "pytest-gefyra"],
        )
        self.operator.wait(
            "gefyraclients.gefyra.dev/client-a",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )

        self.cmd(
            "run",
            [
                "-i",
                self.demo_backend_image,
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
        self.operator.wait(
            "gefyrabridgemounts.gefyra.dev/nginx-deployment-gefyra",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )
        self.operator.wait(
            "deployment/nginx-deployment-gefyra",
            "jsonpath=.spec.template.spec.containers[0].image=nginx:1.14.2",
            namespace="default",
            timeout=60,
        )

        self.assert_get_contains("http://localhost:8080", "Welcome to nginx!")

        # TODO maybe check the new deployment?

        self.cmd(
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

        result = self.operator.kubectl(
            ["get", "gefyrabridges.gefyra.dev", "-n", "gefyra"],
            as_dict=True,
        )

        bridge_name = result["items"][0]["metadata"]["name"]

        self.operator.wait(
            f"gefyrabridges.gefyra.dev/{bridge_name}",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )

        self.assert_get_contains("http://localhost:8080", "Welcome to nginx!")

        self.assert_get_contains(
            "http://localhost:8080", "Hello from Gefyra.", headers={"x-gefyra": "peer"}
        )

    def test_image_deployment_patches(self):
        """
        Test if a deployment image patch is detected and the bridge is updated accordingly.
        """
        client_file_path = self.tmp_path / "client-a.json"
        self.cmd("client", ["config", "-o", client_file_path, "client-a", "--local"])

        self.cmd(
            "connection",
            ["connect", "-f", client_file_path, "--connection-name", "pytest-gefyra"],
        )

        self.cmd(
            "run",
            [
                "-i",
                self.demo_backend_image,
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

        self.operator.kubectl(
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

        self.operator.wait(
            "deployment/nginx-deployment-gefyra",
            "jsonpath=.spec.template.spec.containers[0].image=nginx:latest",
            namespace="default",
            timeout=60,
        )

        # RESTORING state usually lasts just very briefly, so we wait for PREPARING state
        self.operator.wait(
            "gefyrabridgemounts.gefyra.dev/nginx-deployment-gefyra",
            "jsonpath=.state=PREPARING",
            namespace="gefyra",
            timeout=60,
        )

        self.operator.wait(
            "gefyrabridgemounts.gefyra.dev/nginx-deployment-gefyra",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )

        self.assert_get_contains("http://localhost:8080", "Welcome to nginx!")

        self.assert_get_contains(
            "http://localhost:8080", "Hello from Gefyra.", headers={"x-gefyra": "peer"}
        )

    def test_rollout_bridge_mount_reconciles(self):
        """
        Test if a deployment rollout is detected and the bridge is updated accordingly.
        """
        client_file_path = self.tmp_path / "client-a.json"
        self.cmd("client", ["config", "-o", client_file_path, "client-a", "--local"])

        self.cmd(
            "connection",
            ["connect", "-f", client_file_path, "--connection-name", "pytest-gefyra"],
        )

        self.cmd(
            "run",
            [
                "-i",
                self.demo_backend_image,
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

        self.operator.kubectl(
            [
                "rollout",
                "restart",
                "deployment/nginx-deployment",
            ]
        )

        self.operator.wait(
            "gefyrabridgemounts.gefyra.dev/nginx-deployment-gefyra",
            "jsonpath=.state=RESTORING",
            namespace="gefyra",
            timeout=60,
        )

        self.operator.wait(
            "gefyrabridgemounts.gefyra.dev/nginx-deployment-gefyra",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )

        self.assert_get_contains("http://localhost:8080", "Welcome to nginx!")

        self.assert_get_contains(
            "http://localhost:8080", "Hello from Gefyra.", headers={"x-gefyra": "peer"}
        )
