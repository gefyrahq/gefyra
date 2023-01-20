from time import sleep

import docker
from docker.context import ContextAPI
from kubernetes.client import (
    CoreV1Api,
    RbacAuthorizationV1Api,
    AppsV1Api,
    CustomObjectsApi,
)
from kubernetes.config import load_kube_config, ConfigException

from gefyra.__main__ import version
from gefyra.api import down, status, up
from gefyra.api.status import StatusSummary
from gefyra.configuration import default_configuration, ClientConfiguration
import gefyra.configuration as config_package


class GefyraBaseTest:
    provider = None  # minikube or k3d
    params = {}
    kubeconfig = "~/.kube/config"

    def setUp(self):
        if not self.provider:
            raise Exception("No provider set")

        if self.provider == "minikube":
            self.params["minikube"] = "minikube"

        self._init_kube_api()
        self._init_docker()
        return super().setUp()

    def _init_docker(self):
        self.DOCKER_API = docker.from_env()

    def _init_kube_api(self):
        load_kube_config(self.kubeconfig)
        self.K8S_CORE_API = CoreV1Api()
        self.K8S_RBAC_API = RbacAuthorizationV1Api()
        self.K8S_APP_API = AppsV1Api()
        self.K8S_CUSTOM_OBJECT_API = CustomObjectsApi()

    def _deployment_ready(self, deployment):
        return (
            deployment.status.ready_replicas
            and deployment.status.ready_replicas == 1
            and deployment.status.available_replicas == 1
        )

    def assert_operator_ready(self, timeout=60, interval=1):
        counter = 0
        while counter < timeout:
            counter += 1
            operator_deployment = self.K8S_APP_API.read_namespaced_deployment(
                name="gefyra-operator", namespace="gefyra"
            )
            if self._deployment_ready(operator_deployment):
                return True
            sleep(interval)
        raise AssertionError(f"Operator not ready within {timeout} seconds.")

    def assert_stowaway_ready(self, timeout=60, interval=1):
        counter = 0
        while counter < timeout:
            counter += 1
            stowaway_deployment = self.K8S_APP_API.read_namespaced_deployment(
                name="gefyra-stowaway", namespace="gefyra"
            )
            if self._deployment_ready(stowaway_deployment):
                return True
            sleep(interval)
        raise AssertionError(f"Stowaway not ready within {timeout} seconds.")

    def assert_cargo_running(self, timeout=20, interval=1):
        self.assert_container_running("gefyra-cargo", timeout, interval)

    def assert_container_running(self, container: str, timeout=20, interval=1):
        counter = 0
        while counter < timeout:
            container = self.DOCKER_API.containers.get(container)
            if container.status == "running":
                return True
        raise AssertionError(f"{container} not running within {timeout} seconds.")

    def assert_in_container_logs(self, container: str, message: str):
        container = self.DOCKER_API.containers.get(container)
        logs = container.logs()
        if message in logs:
            return True
        raise AssertionError(f"{message} not found in {container} logs.")

    def assert_gefyra_connected(self):
        _status = status(default_configuration)
        self.assertEqual(_status.summary, StatusSummary.UP)
        self.assertEqual(_status.client.cargo, True)
        self.assertEqual(_status.client.network, True)
        self.assertEqual(_status.cluster.operator, True)
        self.assertEqual(_status.cluster.stowaway, True)

    def assert_gefyra_not_connected(self):
        _status = status(default_configuration)
        self.assertEqual(_status.summary, StatusSummary.DOWN)

    def test_run_gefyra_version(self):
        res = version(config_package, True)
        self.assertTrue(res)

    def test_run_gefyra_down_status(self):
        self.assert_gefyra_not_connected()

    def test_run_gefyra_up_with_invalid_kubeconfig_path(self):
        with self.assertRaises(RuntimeError):
            ClientConfiguration(kube_config_file="/tmp/invalid")

    def test_run_gefyra_up_with_invalid_context(self):
        with self.assertRaises(ConfigException):
            c = ClientConfiguration()
            c.KUBE_CONTEXT = "invalid-context"
            c.KUBE_CONTEXT

    def test_run_gefyra_up_in_another_docker_context(self):
        ContextAPI.create_context("another-context")
        ContextAPI.set_current_context("another-context")
        res = up(default_configuration)
        self.assertTrue(res)
        self.assert_operator_ready()
        self.assert_stowaway_ready()
        down()
        ContextAPI.set_current_context("default")

    def test_run_gefyra_up(self):
        res = up(default_configuration)
        self.assertTrue(res)
        self.assert_operator_ready()
        self.assert_stowaway_ready()
        self.assert_cargo_running()
        self.assert_gefyra_connected()

    def test_run_gefyra_up_again_changes_nothing(self):
        pass

    def test_run_gefyra_status_running(self):
        pass

    def test_run_gefyra_run_with_faulty_port_flag(self):
        pass

    def test_run_gefyra_run_with_faulty_env_from_flag(self):
        pass

    def test_run_gefyra_run_with_localhost_port_mapping(self):
        pass

    def test_run_gefyra_run_attached(self):
        pass

    def test_run_gefyra_run_with_no_given_namespace_and_no_fallback(self):
        pass

    def test_run_gefyra_run_with_default_namespace_from_kubeconfig(self):
        pass

    def test_run_gefyra_bridge_with_invalid_deployment(self):
        pass

    def test_run_gefyra_bridge_with_invalid_container(self):
        pass

    def test_run_gefyra_bridge_with_container_with_command(self):
        pass

    def test_run_gefyra_bridge_with_deployment(self):
        pass

    def test_run_gefyra_status_check_containers_and_bridge(self):
        pass

    def test_run_gefyra_unbridge_fails_with_wrong_kubeconfig(self):
        pass

    def test_run_gefyra_unbridge_without_a_flag_and_no_name(self):
        pass

    def test_run_gefyra_bridge_with_deployment_short_name(self):
        pass

    def test_run_gefyra_bridge_with_deployment_short_name_deploy_without_container_name(
        self,
    ):
        pass

    def test_run_gefyra_unbridge(self):
        pass

    def test_run_gefyra_bridge_with_pod(self):
        pass

    def test_run_gefyra_list_bridges(self):
        pass

    def test_run_gefyra_list_containers(self):
        pass

    def test_run_gefyra_down(self):
        pass

    def test_run_gefyra_down_again_without_errors(self):
        pass
