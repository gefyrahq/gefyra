from time import sleep
import unittest

from kubernetes.client import (
    CoreV1Api,
    RbacAuthorizationV1Api,
    AppsV1Api,
    CustomObjectsApi,
)
from kubernetes.config import load_kube_config

from gefyra.__main__ import version
from gefyra.api import status, up
from gefyra.api.status import StatusSummary
from gefyra.configuration import default_configuration


class GefyraBaseTest(unittest.TestCase):
    provider = None  # minikube or k3d
    params = {}
    kubeconfig = "~/.kube/config"
    context = "default"

    def setUp(self):
        if not self.provider:
            raise Exception("No provider set")

        if self.provider == "minikube":
            self.params["minikube"] = "minikube"

        self._init_kube_api()
        return super().setUp()

    def _init_kube_api(self):
        load_kube_config(self.kubeconfig, context=self.context)
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
            stowaway_deployment = self.K8S_APP_API.read_namespaced_deployment(
                name="gefyra-stowaway", namespace="gefyra"
            )
            if self._deployment_ready(stowaway_deployment):
                return True
            sleep(interval)
        raise AssertionError(f"Stowaway not ready within {timeout} seconds.")

    def assert_cargo_running(self):
        pass

    def assert_container_running(self, container: str):
        pass

    def assert_in_container_logs(self, container: str, message: str):
        pass

    def test_run_gefyra_version(self):
        res = version(default_configuration, True)
        self.assertTrue(res)

    def test_run_gefyra_status(self):
        _status = status(default_configuration)
        self.assertEqual(_status.summary, StatusSummary.DOWN)
        # check status content

    def test_run_gefyra_up_with_invalid_kubeconfig_path(self):
        pass

    def test_run_gefyra_up_with_invalid_environment_kubeconfig_path(self):
        pass

    def test_run_gefyra_up_with_invalid_context(self):
        pass

    def test_run_gefyra_up_in_another_docker_context(self):
        pass

    def test_run_gefyra_up(self):
        res = up(default_configuration)
        self.assertTrue(res)
        self.assert_operator_ready()
        self.assert_stowaway_ready()

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
