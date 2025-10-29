from pathlib import Path
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

from click.testing import CliRunner, Result
from copy import deepcopy
import os

from click import BadParameter
from docker.context import ContextAPI
from gefyra.cli.utils import check_connection_name


from gefyra.api.clients import list_client, write_client_file
from gefyra.api.install import LB_PRESETS

from gefyra.api.list import get_bridges_and_print, get_containers_and_print
from gefyra.cli.main import cli
from gefyra.cluster.utils import (
    get_container_command,
    get_container_image,
    get_container_ports,
    get_v1pod,
)
from gefyra.local.bridge import handle_delete_gefyrabridge
from gefyra.types import GefyraClientState

from gefyra.api import (
    create_bridge,
    reflect,
    run,
    status,
    unbridge_all,
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
from tests.conftest import purge_gefyra_objects
from tests.e2e.const import CONNECTION_NAME
from tests.e2e.mixin import GefyraTestMixin

default_configuration = ClientConfiguration()


class GefyraBaseTest(GefyraTestMixin):
    provider = None  # minikube or k3d
    params = {}
    kubeconfig = "~/.kube/config"

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
                "env": ["SOME=ENVVAR"],
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
                "wait": True,
            }
        )
        return params

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
        del params["env"]
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
            create_bridge(**bridge_params)
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
            create_bridge(**bridge_params)
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
            bridge_params["target"] = (
                "deployment/hello-nginxdemo-command/hello-nginx-command"
            )
            bridge_params["namespace"] = "commands"
            create_bridge(**bridge_params)
        self.assertIn("Cannot bridge pod", str(rte.exception))
        self.assertIn("since it has a `command` defined", str(rte.exception))
        self._stop_container(self.default_run_params["name"])

    def test_d_run_gefyra_bridge_with_deployment(self):
        self.assert_cargo_running()
        self.assert_gefyra_connected()
        run_params = self.default_run_params
        del run_params["env_from"]
        run(**run_params)
        res = create_bridge(**self.default_bridge_params)
        self.assertTrue(res)
        self.assert_deployment_ready(
            self.default_bridge_params["namespace"],
            name="hello-nginxdemo",
        )

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
        runner = CliRunner()
        res = runner.invoke(cli, ["unbridge", "--all"], catch_exceptions=False)
        print(res.output)
        self.assertEqual(res.exit_code, 0)
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
        res = create_bridge(**bridge_params)
        self.assertTrue(res)

    def test_h_run_gefyra_unbridge_with_name(self):
        runner = CliRunner()
        res = runner.invoke(
            cli,
            ["unbridge", "mypyserver-to-default.deploy.hello-nginxdemo"],
            catch_exceptions=False,
        )
        self.assertEqual(res.exit_code, 0)
        pod_container_dict = get_pods_and_containers_for_workload(
            default_configuration, "hello-nginxdemo", "default", "deployment"
        )
        pod_name = list(pod_container_dict.keys())[0]
        self.assert_carrier_uninstalled(name=pod_name, namespace="default")
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
        res_bridge = create_bridge(**bridge_params)
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
        res_bridge = create_bridge(**bridge_params)
        self.assertTrue(res_bridge)

    def test_l_run_gefyra_bridge_with_pod_again_fails(self):
        bridge_params = self.default_bridge_params
        pod_container_dict = get_pods_and_containers_for_workload(
            default_configuration, "hello-nginxdemo", "default", "deployment"
        )
        pod_name = list(pod_container_dict.keys())[0]
        bridge_params["target"] = f"pod/{pod_name}/hello-nginx"
        with self.assertRaises(RuntimeError) as rte:
            create_bridge(**bridge_params)

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
            command=["sleep", "300"],
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

        assert "allocated" in str(rte.exception) or "occupied" in str(rte.exception)
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
            ["connections", "connect", "-n", CONNECTION_NAME],
            catch_exceptions=False,
        )
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
                "--command",
                "python3 local.py",
                "--connection-name",
                CONNECTION_NAME,
            ],
            catch_exceptions=False,
        )
        self.assertEqual(res.exit_code, 0)
        self.assert_http_service_available("localhost", 8000)
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()

    def test_s_run_via_cli_with_pull(self):
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
                "quay.io/gefyra/pyserver",
                "--name",
                "mypyserver",
                "--namespace",
                "default",
                "--expose",
                "8000:8000",
                "--detach",
                "--rm",
                "--command",
                "python3 local.py",
                "--connection-name",
                CONNECTION_NAME,
                "--pull",
                "always",
            ],
            catch_exceptions=False,
        )
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Pulling image", res.output)
        self.assert_http_service_available("localhost", 8000)
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()

    def test_s_run_via_cli_without_connection_name(self):
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
                "--command",
                "python3 local.py",
            ],
            catch_exceptions=False,
        )

        self.assertEqual(res.exit_code, 0)
        self.assert_http_service_available("localhost", 8000)
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()

    def test_t_install_presets(self):
        runner = CliRunner()
        res = runner.invoke(
            cli,
            ["install", "--preset", "aws", "--apply", "--wait"],
            catch_exceptions=False,
        )
        self.assertEqual(res.exit_code, 0)
        self.assert_pod_ready("gefyra-stowaway-0", "gefyra", 30)
        self.assert_service_available("gefyra-stowaway-wireguard", "gefyra")
        self.assert_service_has_annotations(
            "gefyra-stowaway-wireguard", "gefyra", LB_PRESETS["aws"].service_annotations
        )
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()

    def test_u_unsupported_probes_throw_error(self, operator: AClusterManager):
        res = self.gefyra_up()
        self.assertTrue(res)
        self.assert_gefyra_connected()

        # apply failing workload
        operator.apply("../../operator/tests/fixtures/demo_pods_not_supported.yaml")

        runner = CliRunner()
        res = runner.invoke(
            cli,
            [
                "bridge",
                "-N",
                "test",
                "-n",
                "demo-failing",
                "--target",
                "deployment/frontend/frontend",
                "--ports",
                "80:8080",
                "--connection-name",
                CONNECTION_NAME,
            ],
        )

        self.assert_gefyra_client_state("client-a", GefyraClientState.ERROR)

    def test_util_for_connection_check(self):
        res = self.gefyra_up()
        self.assertTrue(res)
        self.assert_cargo_running()
        self.assert_gefyra_connected()

        assert check_connection_name(None, None, CONNECTION_NAME) == CONNECTION_NAME

        with self.assertRaises(BadParameter) as rte:
            check_connection_name(None, None, "something")
        self.assertIn("does not exist", str(rte.exception))

        assert check_connection_name(None, None) == CONNECTION_NAME
        self.gefyra_down()
        self.assert_namespace_not_found("gefyra")
        self.assert_cargo_not_running()

    def test_util_for_pod_not_found(self):
        with self.assertRaises(RuntimeError) as rte:
            get_pods_and_containers_for_pod_name(
                config=default_configuration, name="foo", namespace="default"
            )
        self.assertIn("Pod foo not found.", str(rte.exception))

    def test_v_client_connect_params_precedence(self):
        runner = CliRunner()
        self.gefyra_up()
        self.assert_gefyra_client_state(
            client_id=CONNECTION_NAME, state=GefyraClientState.ACTIVE
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
            ["connections", "connect", "-n", CONNECTION_NAME, "--mtu", "1200"],
            catch_exceptions=False,
        )
        self.assertEqual(res.exit_code, 0)

        clients = list_client()

        applied_config = clients[0].get_client_config(gefyra_server="127.0.0.1:31820")

        self.assertEqual(applied_config.WIREGUARD_MTU, "1200")


LOCAL_CONTAINER_NAME = "gefyra-new-backend"


@pytest.mark.parametrize(
    "operator", ["operator_no_sa", "operator_with_sa"], indirect=True
)
class GefyraTestCase:
    provider = "k3d"

    @pytest.fixture(autouse=True)
    def _capture_request(self, request):
        self._request = request

    @pytest.fixture(scope="class", autouse=True)
    def _init_docker(self):
        self.DOCKER_API = docker.from_env()
        return self.DOCKER_API

    @pytest.fixture(autouse=True)
    def _init_kube_api(self, operator: AClusterManager):
        load_kube_config(str(operator.kubeconfig))
        self.K8S_CORE_API = CoreV1Api()
        self.K8S_RBAC_API = RbacAuthorizationV1Api()
        self.K8S_APP_API = AppsV1Api()
        self.K8S_CUSTOM_OBJECT_API = CustomObjectsApi()

    @pytest.fixture(autouse=True)
    def _remove_containers(self, _init_docker):
        yield
        containers = ["gefyra-cargo-pytest-gefyra", LOCAL_CONTAINER_NAME]
        for container in containers:
            try:
                _init_docker.containers.get(container).remove(force=True)
            except docker.errors.NotFound:
                pass

    def cmd(self, kubeconfig: Path, command: str, params: List[str]) -> Result:
        load_kube_config(str(kubeconfig))
        from gefyra.cli.main import cli

        runner = CliRunner()
        if kubeconfig:
            res = runner.invoke(
                cli,
                ["--kubeconfig", str(kubeconfig), command, *params],
                catch_exceptions=True,
            )
        else:
            res = runner.invoke(
                cli,
                [command, *params],
                catch_exceptions=True,
            )
        if res.exit_code != 0:
            import traceback

            raise AssertionError(
                f"Command failed: {res.output}\nExit code: "
                + str(res.exit_code)
                + "\nTrace: "
                + str(traceback.format_exception(res.exception))
            )
        return res

    def run_operator_with_sa(self, operator: AClusterManager) -> bool:
        no_sa = operator.kubectl(
            [
                "-n",
                "gefyra",
                "get",
                "deploy",
                "gefyra-operator",
                "-o=jsonpath='{.spec.template.spec.containers[0].env[?(@.name==\"GEFYRA_DISABLE_CLIENT_SA_MANAGEMENT\")].value}'",
            ],
            as_dict=False,
        )
        if no_sa and no_sa == "True":
            return True
        return False

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
