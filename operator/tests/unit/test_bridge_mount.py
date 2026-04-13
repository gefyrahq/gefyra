import json
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, DEFAULT, patch

from kubernetes.client import V1Deployment, V1Probe

import logging

from tests.utils import post_event_noop

from ..factories import (
    NginxDeploymentFactory,
    NginxPodFactory,
    V1ConfigMapFactory,
    V1PodListFactory,
    V1ProbeFactory,
    V1ServiceFactory,
)

from gefyra.configuration import OperatorConfiguration

logger = logging.getLogger(__name__)


class TestBridgeMountSync(TestCase):
    def test_bridge_mount_label_duplication(self):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        mount = Carrier2BridgeMount(
            name="test",
            configuration=None,
            target_namespace="default",
            target="deploy/nginx",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=None,
        )

        labels = mount._get_duplication_labels({"app": "nginx"})
        self.assertEqual(labels, {"app": "nginx-gefyra"})

    def test_bridge_mount_deployment_cloning(self):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount
        from kubernetes.client import (
            V1Deployment as _V1Deployment,
            V1DeploymentSpec,
            V1ObjectMeta,
            V1LabelSelector,
            V1PodTemplateSpec,
            V1PodSpec,
            V1Container,
            V1ContainerPort,
        )

        mount = Carrier2BridgeMount(
            name="test",
            configuration=None,
            target_namespace="default",
            target="deploy/nginx",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=None,
        )

        # Build deployment from the same kubernetes module version as
        # carrier2mount to avoid isinstance mismatch after module reload
        deployment = _V1Deployment(
            metadata=V1ObjectMeta(name="nginx", labels={"app": "nginx"}),
            spec=V1DeploymentSpec(
                selector=V1LabelSelector(match_labels={"app": "nginx"}),
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(name="", labels={"app": "nginx"}),
                    spec=V1PodSpec(
                        containers=[
                            V1Container(
                                name="nginx",
                                image="nginx",
                                ports=[V1ContainerPort(container_port=80)],
                            )
                        ]
                    ),
                ),
            ),
        )

        new_workload = mount._clone_workload_structure(deployment)
        self.assertEqual(new_workload.metadata.name, "nginx-gefyra")
        self.assertIn(("app", "nginx-gefyra"), new_workload.metadata.labels.items())
        self.assertIn(
            ("app", "nginx-gefyra"), new_workload.spec.selector.match_labels.items()
        )
        self.assertIn(
            ("app", "nginx-gefyra"),
            new_workload.spec.template.metadata.labels.items(),
        )

    def test_cleaning_annotations(self):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        mount = Carrier2BridgeMount(
            name="test",
            configuration=None,
            target_namespace="default",
            target="deploy/nginx",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=None,
        )

        annotations = {
            "kubectl.kubernetes.io/last-applied-configuration": "some-value",
            "deployment.kubernetes.io/revision": "some-value",
            "some-other-key": "some-value",
        }

        cleaned_annotations = mount._clean_annotations(annotations)
        self.assertEqual(cleaned_annotations, {"some-other-key": "some-value"})


class TestBridgeMountObject(IsolatedAsyncioTestCase):
    @patch("gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api")
    @patch.multiple(
        "gefyra.bridge_mount.carrier2mount",
        app=DEFAULT,
        core_v1_api=DEFAULT,
        custom_object_api=DEFAULT,
    )
    async def test_carrier_patch(
        self, autoscaling_api, app, core_v1_api, custom_object_api
    ):
        from kubernetes.client import ApiException as _ApiExc

        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        def _read_deployment(name, namespace):
            if name == "nginx":
                return NginxDeploymentFactory()
            # Shadow does not exist yet on first prepare().
            raise _ApiExc(status=404)

        app.read_namespaced_deployment.side_effect = _read_deployment
        pod = NginxPodFactory()
        core_v1_api.read_namespaced_pod_status.return_value = pod
        core_v1_api.list_namespaced_pod.return_value = V1PodListFactory(items=[pod])
        custom_object_api.get_namespaced_custom_object.return_value = {
            "target": "nginx-deployment",
        }
        # No HPA on the source.
        autoscaling_api.return_value.list_namespaced_horizontal_pod_autoscaler.return_value.items = (
            []
        )

        mount = Carrier2BridgeMount(
            name="test",
            configuration=OperatorConfiguration(),
            target_namespace="default",
            target="deploy/nginx",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=logger,
        )
        await mount.prepare()
        # One read for the source, one for the (missing) shadow.
        self.assertEqual(app.read_namespaced_deployment.call_count, 2)
        app.create_namespaced_deployment.assert_called_once()
        # Hash annotation is persisted on the created shadow.
        create_body = app.create_namespaced_deployment.call_args[0][1]
        from gefyra.bridge_mount.carrier2mount.source_hash import (
            SOURCE_WORKLOAD_HASH_ANNOTATION,
        )

        self.assertIn(
            SOURCE_WORKLOAD_HASH_ANNOTATION, create_body.metadata.annotations
        )

        app.reset_mock()

        custom_object_api.list_namespaced_custom_object.return_value = {"items": []}
        # Mock carrier config return
        carrier_config = AsyncMock()
        carrier_config.add_bridge_rules_for_mount._return_value_ = True
        mount._set_carrier_upstream = carrier_config

        await mount.install()  # Await
        core_v1_api.patch_namespaced_pod.assert_called_once()
        args = core_v1_api.patch_namespaced_pod.call_args

        cm = V1ConfigMapFactory()
        cm.data = {
            "default-nginx": json.dumps(
                {
                    "originalConfig": {
                        "version": 1,
                    }
                }
            )
        }
        core_v1_api.read_namespaced_config_map.return_value = cm

        core_v1_api.read_namespaced_pod.return_value = pod

        self.assertEqual(
            args[1]["body"].spec.containers[0].image, "quay.io/gefyra/carrier2:latest"
        )

        await mount.uninstall()  # Await
        app.patch_namespaced_deployment.assert_called_once()
        call_args = app.patch_namespaced_deployment.call_args
        body: V1Deployment = call_args[1]["body"]

        assert body.spec.template.metadata.annotations[
            "kubectl.kubernetes.io/restartedAt"
        ]

    @patch("gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api")
    @patch.multiple(
        "gefyra.bridge_mount.carrier2mount",
        app=DEFAULT,
        core_v1_api=DEFAULT,
        custom_object_api=DEFAULT,
    )
    async def test_existing_shadow_without_hash_patches(
        self, autoscaling_api, app, core_v1_api, custom_object_api
    ):
        """When an existing shadow is found but carries no source-hash
        annotation (legacy/foreign), the provider must patch it to catch up."""
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        source = NginxDeploymentFactory()
        legacy_shadow = NginxDeploymentFactory()
        legacy_shadow.metadata.name = "nginx-gefyra"
        # Simulate a pre-existing shadow without the new hash annotation.
        legacy_shadow.metadata.annotations = None

        def _read_deployment(name, namespace):
            return source if name == "nginx" else legacy_shadow

        app.read_namespaced_deployment.side_effect = _read_deployment
        pod = NginxPodFactory()
        core_v1_api.read_namespaced_pod_status.return_value = pod
        core_v1_api.list_namespaced_pod.return_value = V1PodListFactory(items=[pod])
        custom_object_api.get_namespaced_custom_object.return_value = {
            "target": "nginx-deployment",
        }
        from kubernetes.client import ApiException as _ApiExc

        app.patch_namespaced_deployment.return_value = True
        core_v1_api.create_namespaced_service.side_effect = _ApiExc(status=409)
        core_v1_api.patch_namespaced_service.return_value = True
        autoscaling_api.return_value.list_namespaced_horizontal_pod_autoscaler.return_value.items = (
            []
        )

        mount = Carrier2BridgeMount(
            name="test",
            configuration=OperatorConfiguration(),
            target_namespace="default",
            target="deploy/nginx",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=logger,
        )
        await mount.prepare()
        app.patch_namespaced_deployment.assert_called_once()
        # Replicas must not be overwritten on the patch — the shadow HPA owns it.
        patch_body = app.patch_namespaced_deployment.call_args[1]["body"]
        self.assertIsNone(patch_body.spec.replicas)
        core_v1_api.patch_namespaced_service.assert_called_once()
        app.create_namespaced_deployment.assert_not_called()

    @patch("gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api")
    @patch.multiple(
        "gefyra.bridge_mount.carrier2mount",
        app=DEFAULT,
        core_v1_api=DEFAULT,
        custom_object_api=DEFAULT,
    )
    async def test_matching_source_hash_is_noop(
        self, autoscaling_api, app, core_v1_api, custom_object_api
    ):
        """If the shadow already has the same source-hash annotation as the
        current source, no apiserver write for the workload must happen."""
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount
        from gefyra.bridge_mount.carrier2mount.source_hash import (
            SOURCE_WORKLOAD_HASH_ANNOTATION,
            hash_workload_source,
        )

        source = NginxDeploymentFactory()
        current_hash = hash_workload_source(source)

        cached_shadow = NginxDeploymentFactory()
        cached_shadow.metadata.name = "nginx-gefyra"
        cached_shadow.metadata.annotations = {
            SOURCE_WORKLOAD_HASH_ANNOTATION: current_hash,
        }

        def _read_deployment(name, namespace):
            return source if name == "nginx" else cached_shadow

        app.read_namespaced_deployment.side_effect = _read_deployment
        custom_object_api.get_namespaced_custom_object.return_value = {
            "target": "nginx-deployment",
        }
        autoscaling_api.return_value.list_namespaced_horizontal_pod_autoscaler.return_value.items = (
            []
        )

        mount = Carrier2BridgeMount(
            name="test",
            configuration=OperatorConfiguration(),
            target_namespace="default",
            target="deploy/nginx",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=logger,
        )
        await mount.prepare()
        app.create_namespaced_deployment.assert_not_called()
        app.patch_namespaced_deployment.assert_not_called()
        core_v1_api.create_namespaced_service.assert_not_called()
        core_v1_api.patch_namespaced_service.assert_not_called()

    @patch.multiple(
        "gefyra.bridge_mount.carrier2mount",
        core_v1_api=DEFAULT,
    )
    async def test_carrier_upstream(self, core_v1_api):  # Made async
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        mount = Carrier2BridgeMount(
            name="test",
            configuration=OperatorConfiguration(),
            target_namespace="default",
            target="deploy/nginx",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=logger,
        )
        svc = V1ServiceFactory()
        core_v1_api.read_namespaced_service.return_value = svc
        port = svc.spec.ports[0].port
        # config creation works
        probe: V1Probe = V1ProbeFactory()
        carrier_config = await mount._set_carrier_upstream(  # Await
            upstream_ports=[port], probes=[probe]
        )

        assert carrier_config.proxy[0].clusterUpstream == [
            f"nginx-service.default.svc.cluster.local:{port}"
        ]
        assert carrier_config.proxy[0].port == port
        assert carrier_config.probes.httpGet[0] == probe.http_get.port

    @patch.multiple(
        "gefyra.bridge_mount.carrier2mount",
        app=DEFAULT,
        core_v1_api=DEFAULT,
        read_carrier2_config=DEFAULT,
    )
    async def test_upstream_set_property(
        self, app, core_v1_api, read_carrier2_config
    ):  # Made async
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        mount = Carrier2BridgeMount(
            name="test",
            configuration=OperatorConfiguration(),
            target_namespace="default",
            target="deploy/nginx",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=logger,
        )

        # Mock _original_pods with two test pods
        pod1 = NginxPodFactory()
        pod1.metadata.name = "nginx-pod-1"
        pod2 = NginxPodFactory()
        pod2.metadata.name = "nginx-pod-2"

        app.read_namespaced_deployment.return_value = NginxDeploymentFactory()
        core_v1_api.list_namespaced_pod.return_value = V1PodListFactory(
            items=[pod1, pod2]
        )

        core_v1_api.read_namespaced_service.return_value = V1ServiceFactory()

        # Test case 1: no clusterUpstream set
        read_carrier2_config.return_value = [
            "version: 1",
            "threads: 4",
            "pid_file: /tmp/carrier2.pid",
            "error_log: /tmp/carrier.error.log",
            "upgrade_sock: /tmp/carrier2.sock",
            "upstream_keepalive_pool_size: 100",
            "port: 5002",
        ]

        # Await the property
        assert not await mount._upstream_set

        # Test case 2: all clusterUpstream set correctly
        read_carrier2_config.return_value = [
            "version: 1",
            "threads: 4",
            "pid_file: /tmp/carrier2.pid",
            "error_log: /tmp/carrier.error.log",
            "upgrade_sock: /tmp/carrier2.sock",
            "upstream_keepalive_pool_size: 100",
            "port: 5002",
            "proxy:",
            "  - clusterUpstream:",
            "    - 'nginx-service.default.svc.cluster.local:80'",
        ]

        assert await mount._upstream_set  # Await

    async def test_pod_ready_and_healthy(self):  # Made async
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount
        from kubernetes.client import V1ContainerState, V1ContainerStateRunning
        import datetime

        mount = Carrier2BridgeMount(
            name="test",
            configuration=OperatorConfiguration(),
            target_namespace="default",
            target="deploy/nginx",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=logger,
        )

        # Test case 1: Pod with no container statuses
        pod_no_status = NginxPodFactory()
        pod_no_status.status.container_statuses = None
        assert not await mount.pod_ready_and_healthy(pod_no_status, "nginx")  # Await

        # Test case 2: Pod not running
        pod_not_running = NginxPodFactory()
        pod_not_running.status.phase = "Pending"
        assert not await mount.pod_ready_and_healthy(pod_not_running, "nginx")  # Await

        # Test case 3: Container not ready
        pod_not_ready = NginxPodFactory()
        pod_not_ready.status.container_statuses[0].ready = False
        assert not await mount.pod_ready_and_healthy(pod_not_ready, "nginx")  # Await

        # Test case 4: Container not started
        pod_not_started = NginxPodFactory()
        pod_not_started.status.container_statuses[0].started = False
        assert not await mount.pod_ready_and_healthy(pod_not_started, "nginx")  # Await

        # Test case 5: Container state not running
        pod_state_not_running = NginxPodFactory()
        pod_state_not_running.status.container_statuses[0].state = V1ContainerState(
            running=True
        )
        assert not await mount.pod_ready_and_healthy(
            pod_state_not_running, "nginx"
        )  # Await

        # Test case 6: Container running but no started_at time
        pod_no_started_at = NginxPodFactory()
        running_state = V1ContainerStateRunning(started_at=None)
        pod_no_started_at.status.container_statuses[0].state = V1ContainerState(
            running=running_state
        )
        assert not await mount.pod_ready_and_healthy(
            pod_no_started_at, "nginx"
        )  # Await

        # Test case 7: Healthy pod - all conditions met
        healthy_pod = NginxPodFactory()
        healthy_pod.status.phase = "Running"
        healthy_pod.status.container_statuses[0].ready = True
        healthy_pod.status.container_statuses[0].started = True
        running_state = V1ContainerStateRunning(started_at=datetime.datetime.now())
        healthy_pod.status.container_statuses[0].state = V1ContainerState(
            running=running_state
        )
        assert await mount.pod_ready_and_healthy(healthy_pod, "nginx")  # Await
