import pytest

from pytest_kubernetes.providers import AClusterManager

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
                "--cpu",
                "1",
                "--memory",
                "128m",
            ],
        )

        self.assert_get_contains("http://localhost:8000", "Hello from Gefyra.")

        self.assert_get_contains("http://localhost:8080", "Welcome to nginx!")

        self.cmd(
            operator.kubeconfig,
            "mount",
            [
                "create",
                "--name",
                "nginx-deployment-gefyra",
                "--target",
                "deploy/nginx-deployment/nginx",
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
                "create",
                "--local",
                LOCAL_CONTAINER_NAME,
                "--ports",
                "80:8000",
                "--match-header-exact",
                "x-gefyra:peer",
                "--mount",
                "nginx-deployment-gefyra",
                "--connection-name",
                "pytest-gefyra",
                "--name",
                "pytest-gefyra-bridge",
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

        res = self.cmd(
            operator.kubeconfig,
            "bridge",
            ["inspect", "pytest-gefyra-bridge"],
        )

        # Assert the command succeeded (already checked by cmd() but explicit is good)
        assert res.exit_code == 0

        # Assert the bridge name is in the output
        assert "pytest-gefyra-bridge" in res.output

        # Assert the mount target is shown
        assert "nginx-deployment-gefyra" in res.output

        # Assert the header match rule is shown (the x-gefyra:peer header)
        assert "x-gefyra" in res.output

        # Assert states are shown (ACTIVE state should be present since bridge is active)
        assert "States:" in res.output

        # Assert the GefyraBridgeMount reference is shown
        assert "GefyraBridgeMount:" in res.output

        res = self.cmd(
            operator.kubeconfig,
            "bridge",
            ["list", "--connection-name", "pytest-gefyra"],
        )
        # Assert the bridge is listed
        assert "pytest-gefyra-bridge" in res.output
        # Assert state is shown
        assert "ACTIVE" in res.output
        # Assert the mount is shown
        assert "nginx-deployment-gefyra" in res.output

        res = self.cmd(
            operator.kubeconfig,
            "bridge",
            ["delete", "--connection-name", "pytest-gefyra", "pytest-gefyra-bridge"],
        )
        # Assert deletion was successful
        assert "marked for deletion" in res.output

        # Verify the bridge is actually deleted
        import time

        for _ in range(30):
            try:
                operator.kubectl(
                    [
                        "get",
                        "gefyrabridges.gefyra.dev/pytest-gefyra-bridge",
                        "-n",
                        "gefyra",
                    ],
                    as_dict=False,
                )
                time.sleep(2)
            except RuntimeError:
                # Resource not found - deletion successful
                break
        else:
            raise AssertionError("Bridge was not deleted within timeout")
