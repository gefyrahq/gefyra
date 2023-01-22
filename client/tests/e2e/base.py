from copy import deepcopy
import requests
import subprocess
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
from gefyra.api import (
    bridge,
    down,
    run,
    status,
    up,
    unbridge_all,
    unbridge,
    list_containers,
    list_interceptrequests,
)
from gefyra.api.status import StatusSummary
from gefyra.cluster.resources import get_pods_and_containers_for_workload
from gefyra.configuration import default_configuration, ClientConfiguration
import gefyra.configuration as config_package


class GefyraBaseTest:
    provider = None  # minikube or k3d
    params = {}
    kubeconfig = "~/.kube/config"

    @property
    def default_run_params(self):
        params = deepcopy(
            {
                "image": "pyserver",
                "name": "mypyserver",
                "namespace": "default",
                "ports": {"8000": "8000"},
                "env_from": "deployment/hello-nginxdemo",
                "detach": True,
                "auto_remove": True,
            }
        )
        params["config"] = default_configuration
        return params

    @property
    def default_bridge_params(self):
        params = deepcopy(
            {
                "name": "mypyserver",
                "namespace": "default",
                "target": "deployment/hello-nginxdemo/hello-nginx",
                "ports": {"80": "8000"},
            }
        )
        params["config"] = default_configuration
        return params

    def setUp(self):
        if not self.provider:
            raise NotImplementedError("No provider set")

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

    def kubectl(self, *args):
        cmd = ["kubectl"]
        cmd.extend(args)
        return subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )

    def _stop_container(self, container):
        try:
            docker_container = self.DOCKER_API.containers.get(container)
            if docker_container.status == "running":
                docker_container.stop()
            docker_container.remove()
            docker_container.wait()
        except docker.errors.NotFound:
            pass
        except docker.errors.APIError as e:
            if e.status_code == 409:
                try:
                    docker_container.wait()
                except docker.errors.NotFound:
                    pass
            else:
                raise e

    def _deployment_ready(self, deployment):
        return (
            deployment.status.ready_replicas
            and deployment.status.ready_replicas == 1
            and deployment.status.available_replicas == 1
        )

    def assert_container_state(self, container, state, retries=3, interval=1):
        docker_container = self.DOCKER_API.containers.get(container)
        counter = 0
        while counter < retries:
            counter += 1
            if docker_container.status == state:
                return True
            sleep(interval)
        self.assertEqual(docker_container.status, state)

    def assert_docker_container_dns(self, container, dns):
        docker_container = self.DOCKER_API.containers.get(container)
        self.assertIn(dns, docker_container.attrs["HostConfig"]["DnsSearch"])

    def assert_http_service_available(self, domain, port, timeout=60, interval=1):
        counter = 0
        while counter < timeout:
            counter += 1
            try:
                response = requests.get(f"http://{domain}:{port}")
                if response.status_code == 200:
                    return True
            except requests.exceptions.ConnectionError:
                pass
            sleep(interval)
        raise AssertionError(f"Service not available within {timeout} seconds.")

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
            counter += 1
            container = self.DOCKER_API.containers.get(container)
            if container.status == "running":
                return True
            sleep(interval)
        raise AssertionError(f"{container} not running within {timeout} seconds.")

    def assert_in_container_logs(self, container: str, message: str):
        container = self.DOCKER_API.containers.get(container)
        logs = container.logs()
        if message in logs.decode("utf-8"):
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

    def test_a_run_gefyra_version(self):
        res = version(config_package, False)
        self.assertTrue(res)

    def test_a_run_gefyra_down_status(self):
        self.assert_gefyra_not_connected()

    def test_a_run_gefyra_up_with_invalid_kubeconfig_path(self):
        with self.assertRaises(RuntimeError) as rte:
            ClientConfiguration(kube_config_file="/tmp/invalid")
        self.assertIn("KUBE_CONFIG_FILE", str(rte.exception))
        self.assertIn("not found.", str(rte.exception))

    def test_a_run_gefyra_up_with_invalid_context(self):
        with self.assertRaises(ConfigException):
            config = ClientConfiguration(kube_context="invalid-context")
            up(config=config)

    def test_a_run_gefyra_up_in_another_docker_context(self):
        ContextAPI.create_context("another-context")
        ContextAPI.set_current_context("another-context")
        res = up(default_configuration)
        self.assertTrue(res)
        self.assert_operator_ready()
        self.assert_stowaway_ready()
        down()
        ContextAPI.set_current_context("default")
        ContextAPI.remove_context("another-context")

    def test_ab_run_gefyra_up(self):
        res = up(default_configuration)
        self.assertTrue(res)
        self.assert_operator_ready()
        self.assert_stowaway_ready()
        self.assert_cargo_running()
        self.assert_gefyra_connected()

    def test_b_run_gefyra_up_again_changes_nothing(self):
        self.test_ab_run_gefyra_up()

    def test_c_run_gefyra_run_with_faulty_env_from_flag(self):
        run_params = self.default_run_params
        run_params["env_from"] = "noDeployment/hello-nginxdemo"
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        with self.assertRaises(RuntimeError) as rte:
            run(**run_params)
        self.assertIn("Unknown workload type noDeployment", str(rte.exception))

    def test_c_run_gefyra_run_with_localhost_port_mapping(self):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        res = run(**self.default_run_params)
        self.assertTrue(res)
        self.assert_http_service_available("localhost", 8000)
        self._stop_container(self.default_run_params["name"])

    def test_c_run_gefyra_run_attached(self):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        params = self.default_run_params
        params["detach"] = False
        params["image"] = "alpine"
        params["command"] = 'sh -c "echo Hello from Gefyra; sleep 10;"'
        params["name"] = "attachedContainer"
        params["ports"] = {}
        params["auto_remove"] = False
        res = run(**params)
        sleep(12)
        self.assertTrue(res)
        self.assert_in_container_logs("attachedContainer", "Hello from Gefyra")
        self.assert_container_state("attachedContainer", "exited", retries=5)
        self._stop_container("attachedContainer")

    def test_c_run_gefyra_run_with_no_given_namespace_and_no_fallback(self):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        params = self.default_run_params
        del params["namespace"]
        res = run(**params)
        self.assertTrue(res)
        self.assert_docker_container_dns(
            self.default_run_params["name"], "default.svc.cluster.local"
        )
        self._stop_container(self.default_run_params["name"])

    def test_c_run_gefyra_run_with_default_namespace_from_kubeconfig(self):
        self.kubectl("config", "set-context", "--current", "--namespace=fancy")
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        params = self.default_run_params
        del params["namespace"]
        del params["env_from"]
        res = run(**params)
        self.assertTrue(res)
        self.assert_docker_container_dns(
            self.default_run_params["name"], "fancy.svc.cluster.local"
        )
        self._stop_container(self.default_run_params["name"])
        self.kubectl("config", "set-context", "--current", "--namespace=default")

    def test_c_run_gefyra_bridge_with_invalid_deployment(self):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        run_params = self.default_run_params
        run(**run_params)
        with self.assertRaises(RuntimeError) as rte:
            bridge_params = self.default_bridge_params
            bridge_params["target"] = "deployment/hello-nginxdemo-not/hello-nginx"
            bridge(**bridge_params)
        self.assertIn("not found", str(rte.exception))
        self._stop_container(self.default_run_params["name"])

    def test_c_run_gefyra_bridge_with_invalid_container(self):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        run_params = self.default_run_params
        run(**run_params)
        with self.assertRaises(RuntimeError) as rte:
            bridge_params = self.default_bridge_params
            bridge_params["target"] = "deployment/hello-nginxdemo/hello-nginx-not"
            bridge(**bridge_params)
        self.assertIn("Could not find container", str(rte.exception))
        self._stop_container(self.default_run_params["name"])

    def test_c_run_gefyra_bridge_with_container_with_command(self):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        run_params = self.default_run_params
        run(**run_params)
        with self.assertRaises(RuntimeError) as rte:
            bridge_params = self.default_bridge_params
            bridge_params[
                "target"
            ] = "deployment/hello-nginxdemo-command/hello-nginx-command"
            bridge_params["namespace"] = "commands"
            bridge(**bridge_params)
        self.assertIn("Cannot bridge pod", str(rte.exception))
        self.assertIn("since it has a `command` defined", str(rte.exception))
        self._stop_container(self.default_run_params["name"])

    def test_d_run_gefyra_bridge_with_deployment(self):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        run_params = self.default_run_params
        del run_params["env_from"]
        run(**run_params)
        res = bridge(**self.default_bridge_params)
        self.assertTrue(res)

    def test_e_run_gefyra_status_check_containers_and_bridge(self):
        _status = status(default_configuration)
        self.assertEqual(_status.summary, StatusSummary.UP)
        self.assertEqual(_status.client.cargo, True)
        self.assertEqual(_status.client.network, True)
        self.assertEqual(_status.cluster.operator, True)
        self.assertEqual(_status.cluster.stowaway, True)
        self.assertEqual(_status.client.bridges, 1)
        self.assertEqual(_status.client.containers, 1)

    def test_f_run_gefyra_unbridge(self):
        res = unbridge_all(default_configuration, wait=True)
        self.assertTrue(res)
        _status = status(default_configuration)
        self.assertEqual(_status.summary, StatusSummary.UP)
        self.assertEqual(_status.client.cargo, True)
        self.assertEqual(_status.client.network, True)
        self.assertEqual(_status.cluster.operator, True)
        self.assertEqual(_status.cluster.stowaway, True)
        self.assertEqual(_status.client.bridges, 0)
        self.assertEqual(_status.client.containers, 1)
        self._stop_container(self.default_run_params["name"])

    def test_g_run_gefyra_bridge_with_deployment_short_name(self):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        run_params = self.default_run_params
        del run_params["env_from"]
        run(**run_params)
        bridge_params = self.default_bridge_params
        bridge_params["target"] = "deploy/hello-nginxdemo/hello-nginx"
        res = bridge(**bridge_params)
        self.assertTrue(res)

    def test_h_run_gefyra_unbridge_with_name(self):
        res = unbridge(
            name="mypyserver-to-default.deploy.hello-nginxdemo",
            config=default_configuration,
            wait=True,
        )
        self.assertTrue(res)
        _status = status(default_configuration)
        self.assertEqual(_status.summary, StatusSummary.UP)
        self.assertEqual(_status.client.cargo, True)
        self.assertEqual(_status.client.network, True)
        self.assertEqual(_status.cluster.operator, True)
        self.assertEqual(_status.cluster.stowaway, True)
        self.assertEqual(_status.client.bridges, 0)
        self.assertEqual(_status.client.containers, 1)
        self._stop_container(self.default_run_params["name"])

    def test_k_run_gefyra_bridge_with_deployment_short_name_deploy_without_container_name(
        self,
    ):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        run_params = self.default_run_params
        del run_params["env_from"]
        run(**run_params)
        bridge_params = self.default_bridge_params
        bridge_params["target"] = "deployment/hello-nginxdemo"
        res_bridge = bridge(**bridge_params)
        self.assertTrue(res_bridge)
        res_unbridge = unbridge_all(
            config=default_configuration,
            wait=True,
        )
        self.assertTrue(res_unbridge)
        self._stop_container(self.default_run_params["name"])

    def test_l_run_gefyra_bridge_with_pod(self):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        run_params = self.default_run_params
        del run_params["env_from"]
        run(**run_params)
        bridge_params = self.default_bridge_params
        pod_container_dict = get_pods_and_containers_for_workload(
            default_configuration, "hello-nginxdemo", "default", "deployment"
        )
        pod_name = list(pod_container_dict.keys())[0]
        bridge_params["target"] = f"pod/{pod_name}/hello-nginx"
        res_bridge = bridge(**bridge_params)
        self.assertTrue(res_bridge)

    def test_m_run_gefyra_list_bridges(self):
        res = list_interceptrequests(default_configuration)
        self.assertEqual(len(res), 1)

    def test_m_run_gefyra_list_containers(self):
        res = list_containers(default_configuration)
        self.assertEqual(len(res), 1)

    def test_n_run_gefyra_down(self):
        res = down(default_configuration)
        self.assertTrue(res)
        _status = status(default_configuration)
        self.assertEqual(_status.summary, StatusSummary.DOWN)
        self.assertEqual(_status.client.cargo, False)
        self.assertEqual(_status.client.network, False)
        self.assertEqual(_status.cluster.operator, False)
        self.assertEqual(_status.cluster.stowaway, False)
        self.assertEqual(_status.client.bridges, 0)
        self.assertEqual(_status.client.containers, 0)

    def test_n_run_gefyra_down_again_without_errors(self):
        self.test_n_run_gefyra_down()
