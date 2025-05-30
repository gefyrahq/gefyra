import subprocess
from time import sleep
import unittest
import docker
from gefyra.api import status
from gefyra.types import GefyraClientState, StatusSummary
import requests

from kubernetes.config import load_kube_config
from kubernetes.client import (
    V1Pod,
    V1Service,
    V1ObjectMeta,
    CoreV1Api,
    RbacAuthorizationV1Api,
    AppsV1Api,
    CustomObjectsApi,
)
from kubernetes.client import ApiException

from click.testing import CliRunner

from gefyra.cli.main import cli
from tests.e2e.const import CONNECTION_NAME


class GefyraTestMixin(unittest.TestCase):
    kubeconfig = "~/.kube/config"

    def _init_docker(self):
        self.DOCKER_API = docker.from_env()

    def _init_kube_api(self):
        load_kube_config(self.kubeconfig)
        print(self.kubeconfig)
        self.K8S_CORE_API = CoreV1Api()
        self.K8S_RBAC_API = RbacAuthorizationV1Api()
        self.K8S_APP_API = AppsV1Api()
        self.K8S_CUSTOM_OBJECT_API = CustomObjectsApi()

    def gefyra_up(self):
        runner = CliRunner()
        res = runner.invoke(cli, ["up"], catch_exceptions=True)
        print(res.output)
        self.assert_gefyra_namespace_ready()
        self.assert_operator_ready()
        self.assert_stowaway_ready()
        self.assert_cargo_running()
        return True

    def gefyra_down(self):
        runner = CliRunner()
        runner.invoke(cli, ["down"], catch_exceptions=False)
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()
        return True

    def tearDown(self):
        docker.ContextAPI.set_current_context("default")
        try:
            docker.ContextAPI.remove_context("another-context")
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

    def assert_service_available(
        self, name: str, namespace: str, retries=30, interval=1
    ):
        counter = 0
        while counter < retries:
            counter += 1
            try:
                self.K8S_CORE_API.read_namespaced_service(
                    name=name, namespace=namespace
                )
            except ApiException as e:
                if e.status == 404:
                    sleep(interval)
                    continue
                else:
                    raise e
            return True
        raise AssertionError(f"Service {name} not available within {retries} retries.")

    def assert_service_has_annotations(
        self, name: str, namespace: str, annotations: dict
    ):
        service: V1Service = self.K8S_CORE_API.read_namespaced_service(
            name=name, namespace=namespace
        )
        metadata: V1ObjectMeta = service.metadata
        for key in annotations.keys():
            self.assertIn(key, metadata.annotations)
            self.assertEqual(annotations[key], metadata.annotations[key])
        return True

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

    def assert_cargo_running(self, timeout=30, interval=1):
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
            sleep(interval)
            try:
                container_obj = self.DOCKER_API.containers.get(container)
            except docker.errors.NotFound:
                continue
            if container_obj.status == "running":
                return True
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

    def _get_pod_startswith(self, pod_name, namespace):
        pods = self.K8S_CORE_API.list_namespaced_pod(namespace=namespace)
        for pod in pods.items:
            if pod_name in pod.metadata.name:
                return pod
        return None
