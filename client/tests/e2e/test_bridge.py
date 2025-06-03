from time import sleep
from typing import List
import docker
import docker.errors
from kubernetes.config import load_kube_config

import requests

from kubernetes.client import (
    CoreV1Api,
    RbacAuthorizationV1Api,
    AppsV1Api,
    CustomObjectsApi,
)
from pytest_kubernetes.providers import AClusterManager
import pytest
from unittest import TestCase

from click.testing import CliRunner

LOCAL_CONTAINER_NAME = "gefyra-new-backend"


@pytest.mark.usefixtures("operator")
@pytest.mark.usefixtures("tmp_path")
@pytest.mark.usefixtures("demo_backend_image")
class GefyraBridgeTest(TestCase):
    provider = "k3d"

    @pytest.fixture(autouse=True)
    def _capture_request(self, request):
        self._request = request

    def _init_docker(self):
        self.DOCKER_API = docker.from_env()

    def _init_kube_api(self):
        load_kube_config(self.kubeconfig)
        self.K8S_CORE_API = CoreV1Api()
        self.K8S_RBAC_API = RbacAuthorizationV1Api()
        self.K8S_APP_API = AppsV1Api()
        self.K8S_CUSTOM_OBJECT_API = CustomObjectsApi()

    def setUp(self):
        self.operator: AClusterManager = self._request.getfixturevalue("operator")
        self.tmp_path = self._request.getfixturevalue("tmp_path")
        self.demo_backend_image = self._request.getfixturevalue("demo_backend_image")
        self.kubeconfig = str(self.operator.kubeconfig)
        self._init_kube_api()
        self._init_docker()
        self.operator.apply("tests/fixtures/nginx_exposed.yaml")

    def tearDown(self):
        containers = ["gefyra-cargo-pytest-gefyra", LOCAL_CONTAINER_NAME]
        for container in containers:
            try:
                self.DOCKER_API.containers.get(container).remove(force=True)
            except docker.errors.NotFound:
                pass
        return super().tearDown()

    def cmd(self, command: str, params: List[str]):
        load_kube_config(self.kubeconfig)
        from gefyra.cli.main import cli

        runner = CliRunner()
        res = runner.invoke(
            cli,
            ["--kubeconfig", str(self.operator.kubeconfig), command, *params],
            catch_exceptions=True,
        )
        if res.exit_code != 0:
            raise AssertionError(
                f"Command failed: {res.output}\nExit code: " + str(res.exit_code)
            )
        return res

    def assert_get_contains(
        self, url: str, expected_content: str, retries: int = 10, headers: dict = None
    ):
        """
        Helper function to assert that a GET request to a URL contains expected content.
        Retries the request if the content is not found.
        """
        while retries > 0:
            try:
                response = requests.get(url, headers=headers)
            except Exception:
                continue
            if expected_content in response.text:
                return
            retries -= 1
            sleep(1)
        raise AssertionError(
            f"Expected content '{expected_content}' not found in response from {url}."
        )

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

    def test_rollout_bridge_is_stable(self):
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
