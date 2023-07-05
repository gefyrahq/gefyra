from copy import deepcopy
import os
from click.testing import CliRunner
from gefyra.api.clients import list_client, write_client_file

from gefyra.api.list import get_bridges_and_print, get_containers_and_print
from gefyra.cli.main import cli
from gefyra.cluster.utils import (
    get_container_command,
    get_container_image,
    get_container_ports,
    get_v1pod,
)
from gefyra.local.bridge import handle_delete_gefyrabridge
from gefyra.local.check import probe_docker, probe_kubernetes
from gefyra.types import GefyraClientState
import requests
import subprocess
from time import sleep

import pytest

import docker
from docker.context import ContextAPI
from kubernetes.client import (
    CoreV1Api,
    RbacAuthorizationV1Api,
    AppsV1Api,
    CustomObjectsApi,
    V1Pod,
)
from kubernetes.client import ApiException
from kubernetes.config import load_kube_config

from gefyra.api import (
    bridge,
    reflect,
    run,
    status,
    unbridge_all,
    unbridge,
    list_containers,
    list_gefyra_bridges,
)
from gefyra.api.status import StatusSummary
from gefyra.cluster.resources import (
    get_pods_and_containers_for_pod_name,
    get_pods_and_containers_for_workload,
    owner_reference_consistent,
)
from gefyra.configuration import ClientConfiguration, get_gefyra_config_location

default_configuration = ClientConfiguration()


CONNECTION_NAME = "default"


class GefyraBaseTest:
    provider = None  # minikube or k3d
    params = {}
    kubeconfig = "~/.kube/config"

    def gefyra_up(self):
        runner = CliRunner()
        runner.invoke(cli, ["up"], catch_exceptions=True)
        self.assert_gefyra_namespace_ready()
        self.assert_cargo_running()
        self.assert_operator_ready()
        self.assert_stowaway_ready()
        return True

    def gefyra_down(self):
        runner = CliRunner()
        runner.invoke(cli, ["down"], catch_exceptions=False)
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()
        return True

    @property
    def default_reflect_params(self):
        params = deepcopy(
            {
                "workload": "deploy/bye-nginxdemo-8000",
                "do_bridge": True,
                "auto_remove": True,
                "connection_name": CONNECTION_NAME,
            }
        )
        return params

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
                "connection_name": CONNECTION_NAME,
            }
        )
        return params

    @property
    def default_bridge_params(self):
        params = deepcopy(
            {
                "name": "mypyserver",
                "namespace": "default",
                "target": "deployment/hello-nginxdemo/hello-nginx",
                "ports": {"80": "8000"},
                "connection_name": CONNECTION_NAME,
            }
        )
        return params

    def tearDown(self):
        ContextAPI.set_current_context("default")
        try:
            ContextAPI.remove_context("another-context")
        except docker.errors.ContextNotFound:
            pass
        return super().tearDown()

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
        print(self.kubeconfig)
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

    def assert_pod_ready(self, pod_name: str, namespace: str, retries=3, interval=1):
        counter = 0
        while counter < retries:
            counter += 1
            pod = self.K8S_CORE_API.read_namespaced_pod(
                namespace=namespace, name=pod_name
            )
            if self._pod_ready(pod):
                return True
            sleep(interval)
        raise AssertionError(f"Pod {pod_name} is not ready.")

    def _pod_ready(self, pod: V1Pod):
        return all([c.status == "True" for c in pod.status.conditions]) and all(
            [c.ready for c in pod.status.container_statuses]
        )

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

    def assert_deployment_ready(
        self, namespace: str, name: str, timeout=60, interval=1
    ):
        counter = 0
        while counter < timeout:
            counter += 1
            operator_deployment = self.K8S_APP_API.read_namespaced_deployment(
                name=name, namespace=namespace
            )
            if self._deployment_ready(operator_deployment):
                return True
            sleep(interval)
        raise AssertionError(f"Deployment {name} not ready within {timeout} seconds.")

    def assert_operator_ready(self, timeout=60, interval=1):
        return self.assert_deployment_ready(
            name="gefyra-operator",
            namespace="gefyra",
            timeout=timeout,
            interval=interval,
        )

    def assert_stowaway_ready(self, retries=10, interval=1):
        return self.assert_pod_ready(
            pod_name="gefyra-stowaway-0",
            namespace="gefyra",
            interval=interval,
            retries=retries,
        )

    def assert_namespace_ready(self, namespace, timeout=30, interval=1):
        counter = 0
        while counter < timeout:
            counter += 1
            namespace = self.K8S_CORE_API.read_namespace(name=namespace)
            if namespace.status.phase == "Active":
                return True
            sleep(interval)
        raise AssertionError(f"Namespace not ready within {timeout} seconds.")

    def assert_gefyra_namespace_ready(self, timeout=30, interval=1):
        self.assert_namespace_ready("gefyra", timeout, interval)

    def assert_namespace_not_found(self, name, timeout=30, interval=1):
        counter = 0
        while counter < timeout:
            counter += 1
            try:
                self.K8S_CORE_API.read_namespace(name=name)
            except ApiException as e:
                if e.status == 404:
                    return True
            sleep(interval)
        raise AssertionError(f"Namespace still available within {timeout} seconds.")

    def assert_cargo_running(self, timeout=20, interval=1):
        self.assert_container_running("gefyra-cargo-default", timeout, interval)

    def assert_cargo_not_running(self, timeout=20, interval=1):
        self.assert_container_not_running("gefyra-cargo-default", timeout, interval)

    def assert_custom_object_quantity(
        self,
        group: str,
        plural: str,
        quantity: int,
        version: str,
        timeout=20,
        interval=1,
    ):
        counter = 0
        while counter < timeout:
            counter += 1
            try:
                resources = self.K8S_CUSTOM_OBJECT_API.list_cluster_custom_object(
                    group=group, plural=plural, version=version
                )
                self.assertEqual(len(resources["items"]), quantity)
            except AssertionError:
                sleep(interval)
                continue
            return True
        raise AssertionError(
            f"Quantity {quantity} for {plural} does not match {len(resources)}"
        )

    def assert_container_not_running(self, container: str, timeout=20, interval=1):
        counter = 0
        while counter < timeout:
            counter += 1
            try:
                container_obj = self.DOCKER_API.containers.get(container)
                if container_obj.status != "running":
                    return True
            except docker.errors.NotFound:
                return True
            sleep(interval)
        raise AssertionError(f"{container} is still running after {timeout} seconds.")

    def assert_container_running(self, container: str, timeout=20, interval=1):
        counter = 0
        while counter < timeout:
            counter += 1
            container_obj = self.DOCKER_API.containers.get(container)
            if container_obj.status == "running":
                return True
            sleep(interval)
        raise AssertionError(f"{container} not running within {timeout} seconds.")

    def assert_in_container_logs(self, container: str, message: str):
        container = self.DOCKER_API.containers.get(container)
        logs = container.logs()
        if message in logs.decode("utf-8"):
            return True
        raise AssertionError(f"{message} not found in {container} logs.")

    def assert_gefyra_connected(self, _status=None):
        if not _status:
            _status = status(connection_name=CONNECTION_NAME)
        self.assertEqual(_status.summary, StatusSummary.UP)
        self.assertEqual(_status.client.cargo, True)
        self.assertEqual(_status.client.network, True)
        self.assertEqual(_status.cluster.operator, True)
        self.assertEqual(_status.cluster.stowaway, True)

    def assert_gefyra_not_connected(self):
        _status = status()
        self.assertEqual(_status.summary, StatusSummary.DOWN)

    def assert_carrier_uninstalled(
        self, name: str, namespace: str, interval=1, retries=30
    ):
        counter = 0
        while counter < retries:
            counter += 1
            pod: V1Pod = self.K8S_CORE_API.read_namespaced_pod(
                name=name, namespace=namespace
            )
            if "gefyra/carrier" not in pod.spec.containers[0].image:
                return True
            sleep(interval)
        raise AssertionError(
            f"Carrier not uninstalled within {retries} retries with interval {interval}s."
        )

    def assert_gefyra_operational_no_bridge(self, connection_name=CONNECTION_NAME):
        _status = status(connection_name=connection_name)
        self.assert_gefyra_connected(_status)
        self.assertEqual(_status.client.bridges, 0)
        self.assertEqual(_status.client.containers, 1)

    def assert_gefyra_client_state(
        self, client_id: str, state: GefyraClientState, timeout=20, interval=1
    ):
        counter = 0
        while counter < timeout:
            counter += 1
            try:
                client = self.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
                    group="gefyra.dev",
                    plural="gefyraclients",
                    version="v1",
                    name=client_id,
                    namespace="gefyra",
                )
                self.assertEqual(client["state"], str(state.value))
            except AssertionError:
                sleep(interval)
                continue
            return True
        raise AssertionError(
            f"Client state is {client['state']} expected {state.value}."
        )

    def test_docker_probe(self):
        res = probe_docker()
        self.assertTrue(res)

    def test_kubernetes_probe(self):
        res = probe_kubernetes()
        self.assertTrue(res)

    def _get_pod_startswith(self, pod_name, namespace):
        pods = self.K8S_CORE_API.list_namespaced_pod(namespace=namespace)
        for pod in pods.items:
            if pod_name in pod.metadata.name:
                return pod
        return None

    def test_get_container_command_error(self):
        config = ClientConfiguration()
        namespace = "default"
        pod_container_dict = get_pods_and_containers_for_workload(
            config, "hello-nginxdemo", namespace, "deployment"
        )
        pod_name = list(pod_container_dict.keys())[0]
        pod = get_v1pod(config=config, namespace=namespace, pod_name=pod_name)
        with self.assertRaises(RuntimeError) as rte:
            get_container_command(pod=pod, container_name="UnknownContainer")
        self.assertIn("Container UnknownContainer not found", str(rte.exception))

    def test_get_container_image_error(self):
        config = ClientConfiguration()
        namespace = "default"
        pod_container_dict = get_pods_and_containers_for_workload(
            config, "hello-nginxdemo", namespace, "deployment"
        )
        pod_name = list(pod_container_dict.keys())[0]
        pod = get_v1pod(config=config, namespace=namespace, pod_name=pod_name)
        with self.assertRaises(RuntimeError) as rte:
            get_container_image(pod=pod, container_name="UnknownContainer")
        self.assertIn("Container UnknownContainer not found", str(rte.exception))

    def test_get_container_ports_error(self):
        config = ClientConfiguration()
        namespace = "default"
        pod_container_dict = get_pods_and_containers_for_workload(
            config, "hello-nginxdemo", namespace, "deployment"
        )
        pod_name = list(pod_container_dict.keys())[0]
        pod = get_v1pod(config=config, namespace=namespace, pod_name=pod_name)
        with self.assertRaises(RuntimeError) as rte:
            get_container_ports(pod=pod, container_name="UnknownContainer")
        self.assertIn("Container UnknownContainer not found", str(rte.exception))

    def test_a_run_gefyra_down_status(self):
        self.assert_gefyra_not_connected()

    def test_a_run_gefyra_up_with_invalid_kubeconfig_path(self):
        with self.assertRaises(RuntimeError) as rte:
            ClientConfiguration(kube_config_file="/tmp/invalid")
        self.assertIn("KUBE_CONFIG_FILE", str(rte.exception))
        self.assertIn("not found.", str(rte.exception))

    # def test_a_run_gefyra_up_with_invalid_context(self):
    #     with self.assertRaises(ConfigException):
    #         config = ClientConfiguration(kube_context="invalid-context")
    #         self.gefyra_up()

    def test_a_run_gefyra_up_in_another_docker_context(self):
        ContextAPI.create_context("another-context")
        ContextAPI.set_current_context("another-context")
        res = self.gefyra_up()
        self.assertTrue(res)
        self.assert_cargo_running()
        self.assert_operator_ready()
        self.assert_stowaway_ready()
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()

    def test_ab_run_gefyra_up(self):
        res = self.gefyra_up()
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
        self.assert_container_state("attachedContainer", "exited", retries=15)
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

    # def test_c_run_gefyra_run_with_default_namespace_from_kubeconfig(self):
    #     self.kubectl("config", "set-context", "--current", "--namespace=fancy")
    #     self.assert_cargo_running()
    #     self.assert_gefyra_connected()
    #     params = self.default_run_params
    #     del params["namespace"]
    #     del params["env_from"]
    #     res = run(**params)
    #     self.assertTrue(res)
    #     self.assert_docker_container_dns(
    #         self.default_run_params["name"], "fancy.svc.cluster.local"
    #     )
    #     self._stop_container(self.default_run_params["name"])
    #     self.kubectl("config", "set-context", "--current", "--namespace=default")

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
        self.caplog.set_level("DEBUG")
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
        _status = status(connection_name=CONNECTION_NAME)
        self.assertEqual(_status.summary, StatusSummary.UP)
        self.assertEqual(_status.client.cargo, True)
        self.assertEqual(_status.client.network, True)
        self.assertEqual(_status.cluster.operator, True)
        self.assertEqual(_status.cluster.stowaway, True)
        self.assertEqual(_status.client.bridges, 1)
        self.assertEqual(_status.client.containers, 1)

    def test_f_run_gefyra_unbridge(self):
        res = unbridge_all(wait=True, connection_name=CONNECTION_NAME)
        self.assertTrue(res)
        self.assert_gefyra_operational_no_bridge()
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
            wait=True,
        )
        pod_container_dict = get_pods_and_containers_for_workload(
            default_configuration, "hello-nginxdemo", "default", "deployment"
        )
        pod_name = list(pod_container_dict.keys())[0]
        self.assert_carrier_uninstalled(name=pod_name, namespace="default")
        self.assertTrue(res)
        self.assert_gefyra_operational_no_bridge()
        self._stop_container(self.default_run_params["name"])

    def test_h_run_gefyra_unbridge_with_name_not_exists(self):
        self.caplog.set_level("DEBUG")
        res = handle_delete_gefyrabridge(
            name="mypyserver-to-default.deploy.hello-nginxdemo-not",
            config=default_configuration,
        )
        self.assertFalse(res)
        self.assertIn("not found", self.caplog.text)

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

    def test_l_run_gefyra_bridge_with_pod_again_fails(self):
        bridge_params = self.default_bridge_params
        pod_container_dict = get_pods_and_containers_for_workload(
            default_configuration, "hello-nginxdemo", "default", "deployment"
        )
        pod_name = list(pod_container_dict.keys())[0]
        bridge_params["target"] = f"pod/{pod_name}/hello-nginx"
        with self.assertRaises(RuntimeError) as rte:
            bridge(**bridge_params)

        self.assertIn("already bridged", str(rte.exception))

    def test_m_run_gefyra_list_bridges(self):
        res = list_gefyra_bridges(connection_name=CONNECTION_NAME)
        self.assertEqual(len(res), 1)

    def test_m_run_gefyra_list_containers(self):
        res = list_containers(connection_name=CONNECTION_NAME)
        self.assertEqual(len(res), 1)

    @pytest.fixture(autouse=True)
    def capsys(self, capsys):
        self.capsys = capsys

    @pytest.fixture(autouse=True)
    def caplog(self, caplog):
        self.caplog = caplog

    @pytest.fixture(autouse=True)
    def monkeypatch(self, monkeypatch):
        self.monkeypatch = monkeypatch

    def test_m_run_gefyra_list_output_bridges(self):
        get_bridges_and_print(connection_name=CONNECTION_NAME)
        captured = self.capsys.readouterr()
        self.assertIn("mypyserver-to-default.pod.hello-nginxdemo", captured.out)

    def test_m_run_gefyra_list_output_containers(self):
        get_containers_and_print(connection_name=CONNECTION_NAME)
        captured = self.capsys.readouterr()
        self.assertIn(self.default_run_params["name"], captured.out)

    def test_m_ownership_reference_check(self):
        wrong_pod = self._get_pod_startswith("gefyra-stowaway", "gefyra")
        deployment = self.K8S_APP_API.read_namespaced_deployment(
            name="hello-nginxdemo", namespace="default"
        )
        right_pod = self._get_pod_startswith("hello-nginxdemo", "default")
        self.assertFalse(
            owner_reference_consistent(wrong_pod, deployment, default_configuration)
        )
        self.assertTrue(
            owner_reference_consistent(right_pod, deployment, default_configuration)
        )

    def test_n_run_gefyra_cluster_down(self):
        self._stop_container(self.default_run_params["name"])
        res = self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()
        self.assertTrue(res)
        _status = status(connection_name=CONNECTION_NAME)
        self.assertEqual(_status.summary, StatusSummary.DOWN)
        self.assertEqual(_status.client.cargo, False)
        self.assertEqual(_status.client.network, False)
        self.assertEqual(_status.cluster.operator, False)
        self.assertEqual(_status.cluster.stowaway, False)
        self.assertEqual(_status.client.bridges, 0)
        self.assertEqual(_status.client.containers, 0)
        self.assert_namespace_not_found("gefyra")

    def test_n_run_gefyra_down_again_without_errors(self):
        self.gefyra_down()

    def test_o_reflect_occupied_port(self):
        container_name = "busybox"
        self.DOCKER_API.containers.run(
            "alpine",
            auto_remove=True,
            ports={"8000/tcp": [8000]},
            detach=True,
            command=["sleep", "40"],
            name=container_name,
        )
        res = self.gefyra_up()
        self.assertTrue(res)
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        self.assert_deployment_ready(name="bye-nginxdemo-8000", namespace="default")
        params = {
            "workload": "deploy/bye-nginxdemo-8000",
            "do_bridge": True,
            "auto_remove": True,
        }
        with self.assertRaises(RuntimeError) as rte:
            reflect(**params)

        self.assertIn("occupied", str(rte.exception))
        self._stop_container(container=container_name)
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()

    def test_p_reflect(self):
        res = self.gefyra_up()
        self.assertTrue(res)
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        self.assert_deployment_ready(name="bye-nginxdemo-8000", namespace="default")
        res_reflect = reflect(**self.default_reflect_params)
        self.assertTrue(res_reflect)
        unbridge_all(connection_name=CONNECTION_NAME, wait=True)
        self.assert_gefyra_operational_no_bridge()
        self._stop_container(
            container="gefyra-reflect-default-deploy-bye-nginxdemo-8000"
        )
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()
        self.assertTrue(res)

    def test_p_reflect_port_overwrite(self):
        res = self.gefyra_up()
        self.assertTrue(res)
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        self.assert_deployment_ready(name="bye-nginxdemo-8000", namespace="default")
        params = self.default_reflect_params
        params.update(
            {
                "ports": {80: 4000},
                "expose_ports": False,
            }
        )
        res_reflect = reflect(**params)
        self.assertTrue(res_reflect)
        self.assert_http_service_available("localhost", 4000)

        unbridge_all(connection_name=CONNECTION_NAME, wait=True)
        self.assert_gefyra_operational_no_bridge()
        self._stop_container(
            container="gefyra-reflect-default-deploy-bye-nginxdemo-8000"
        )
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()
        self.assertTrue(res)

    def test_p_reflect_image_overwrite(self):
        res = self.gefyra_up()
        self.assertTrue(res)
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        self.assert_deployment_ready(name="bye-nginxdemo-8000", namespace="default")
        image = "pyserver:latest"
        params = self.default_reflect_params
        params.update(
            {
                "image": image,
            }
        )
        res_reflect = reflect(**params)
        self.assertTrue(res_reflect)
        container = list(
            filter(
                lambda container: container.name.startswith("gefyra-reflect-"),
                self.DOCKER_API.containers.list(),
            )
        )[0]
        self.assertEqual(container.image.tags[0], image)
        unbridge_all(connection_name=CONNECTION_NAME, wait=True)
        self.assert_gefyra_operational_no_bridge()
        self._stop_container(
            container="gefyra-reflect-default-deploy-bye-nginxdemo-8000"
        )
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()
        self.assertTrue(res)

    def test_o_client_commands(self):
        res = self.gefyra_up()
        self.assertTrue(res)
        self.assert_cargo_running()
        self.assert_gefyra_connected()

        self.assert_custom_object_quantity(
            group="gefyra.dev", plural="gefyraclients", version="v1", quantity=1
        )

        runner = CliRunner()
        res = runner.invoke(
            cli, ["client", "create", "-n", "2"], catch_exceptions=False
        )

        self.assertEqual(res.exit_code, 0)

        clients = list_client()
        self.assert_custom_object_quantity(
            group="gefyra.dev", plural="gefyraclients", version="v1", quantity=3
        )

        res = runner.invoke(
            cli, ["client", "rm", clients[0].client_id], catch_exceptions=False
        )
        self.assertEqual(res.exit_code, 0)
        self.assert_custom_object_quantity(
            group="gefyra.dev", plural="gefyraclients", version="v1", quantity=2
        )

        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()
        self.assertTrue(res)

    def test_r_install_uninstall_command(self):
        runner = CliRunner()
        res = runner.invoke(
            cli, ["install", "--apply", "--wait"], catch_exceptions=False
        )
        self.assertEqual(res.exit_code, 0)
        self.assert_gefyra_namespace_ready()
        self.assert_operator_ready()
        self.assert_stowaway_ready()
        res = runner.invoke(cli, ["uninstall", "--force"], catch_exceptions=False)
        self.assertEqual(res.exit_code, 0)
        self.assert_namespace_not_found("gefyra")

    def test_r_reconnect(self):
        runner = CliRunner()
        self.gefyra_up()
        res = runner.invoke(
            cli, ["connections", "disconnect", CONNECTION_NAME], catch_exceptions=False
        )
        self.assertEqual(res.exit_code, 0)
        self.assert_cargo_not_running()
        self.assert_gefyra_client_state(
            client_id=CONNECTION_NAME, state=GefyraClientState.WAITING
        )

        c_file = write_client_file(
            client_id=CONNECTION_NAME,
            host="127.0.0.1",
        )

        file_loc = os.path.join(
            get_gefyra_config_location(),
            f"{CONNECTION_NAME}_client.json",
        )
        fh = open(file_loc, "w+")
        fh.write(c_file)
        fh.seek(0)
        fh.close()
        sleep(10)
        res = runner.invoke(
            cli,
            ["connections", "connect", "-n", CONNECTION_NAME, "-f", file_loc],
            catch_exceptions=False,
        )
        print(res.output)
        self.assertEqual(res.exit_code, 0)
        self.assert_cargo_running()

        res = runner.invoke(cli, ["uninstall", "--force"], catch_exceptions=False)
        self.assertEqual(res.exit_code, 0)
        self.assert_namespace_not_found("gefyra")
        self.gefyra_down()
        self.assert_cargo_not_running()

    def test_s_command_alias_help(self):
        runner = CliRunner()
        res = runner.invoke(cli, ["client", "--help"], catch_exceptions=False)
        print(res.output)
        self.assertIn("rm,remove", res.output)
        self.assertEqual(res.exit_code, 0)

    def test_s_run_via_cli(self):
        res = self.gefyra_up()
        self.assertTrue(res)
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        runner = CliRunner()
        res = runner.invoke(
            cli,
            [
                "run",
                "--image",
                "pyserver",
                "--name",
                "mypyserver",
                "--namespace",
                "default",
                "--expose",
                "8000:8000",
                "--detach",
                "--rm",
                "--connection-name",
                CONNECTION_NAME,
                "--command",
                "python3 local.py",
            ],
            catch_exceptions=False,
        )
        print(res.output)

        self.assertEqual(res.exit_code, 0)
        self.assert_http_service_available("localhost", 8000)
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()

    def test_util_for_pod_not_found(self):
        with self.assertRaises(RuntimeError) as rte:
            get_pods_and_containers_for_pod_name(
                config=default_configuration, name="foo", namespace="default"
            )
        self.assertIn("Pod foo not found.", str(rte.exception))
