from unittest import TestCase
from unittest.mock import DEFAULT, MagicMock, patch

from kubernetes.client import V1Deployment, V1Probe

import logging

from ..factories import (
    NginxDeploymentFactory,
    NginxPodFactory,
    V1PodListFactory,
    V1ProbeFactory,
    V1ServiceFactory,
)

from gefyra.configuration import OperatorConfiguration

logger = logging.getLogger(__name__)


class TestBridgeMountObject(TestCase):
    def test_bridge_mount_label_duplication(self):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        mount = DuplicateBridgeMount(
            name="test",
            configuration=None,
            target_namespace="default",
            target="nginx",
            target_container="nginx",
            logger=None,
        )

        labels = mount._get_duplication_labels({"app": "nginx"})
        self.assertEqual(labels, {"app": "nginx-gefyra"})

    def test_bridge_mount_deployment_cloning(self):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        mount = DuplicateBridgeMount(
            name="test",
            configuration=None,
            target_namespace="default",
            target="nginx",
            target_container="nginx",
            logger=None,
        )

        deployment = NginxDeploymentFactory()

        new_deployment = mount._clone_deployment_structure(deployment)
        self.assertEqual(new_deployment.metadata.name, "nginx-gefyra")
        self.assertEqual(new_deployment.metadata.labels, {"app": "nginx-gefyra"})
        self.assertEqual(
            new_deployment.spec.selector.match_labels, {"app": "nginx-gefyra"}
        )
        self.assertDictContainsSubset(
            {"app": "nginx-gefyra"},
            new_deployment.spec.template.metadata.labels,
        )

    def test_cleaning_annotations(self):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        mount = DuplicateBridgeMount(
            name="test",
            configuration=None,
            target_namespace="default",
            target="nginx",
            target_container="nginx",
            logger=None,
        )

        annotations = {
            "kubectl.kubernetes.io/last-applied-configuration": "some-value",
            "deployment.kubernetes.io/revision": "some-value",
            "some-other-key": "some-value",
        }

        cleaned_annotations = mount._clean_annotations(annotations)
        self.assertEqual(cleaned_annotations, {"some-other-key": "some-value"})

    @patch.multiple(
        "gefyra.bridge_mount.duplicate",
        app=DEFAULT,
        core_v1_api=DEFAULT,
        custom_object_api=DEFAULT,
    )
    def test_carrier_patch(self, app, core_v1_api, custom_object_api):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        app.read_namespaced_deployment.return_value = NginxDeploymentFactory()
        pod = NginxPodFactory()
        core_v1_api.read_namespaced_pod_status.return_value = pod
        core_v1_api.list_namespaced_pod.return_value = V1PodListFactory(items=[pod])
        custom_object_api.get_namespaced_custom_object.return_value = {
            "target": "nginx-deployment",
        }

        mount = DuplicateBridgeMount(
            name="test",
            configuration=OperatorConfiguration(),
            target_namespace="default",
            target="nginx",
            target_container="nginx",
            logger=logger,
        )
        mount.prepare()
        app.read_namespaced_deployment.assert_called_once()
        app.create_namespaced_deployment.assert_called_once()

        app.reset_mock()

        custom_object_api.list_namespaced_custom_object.return_value = {"items": []}
        # Mock carrier config return
        carrier_config = MagicMock()
        carrier_config.add_bridge_rules_for_mount._return_value_ = True
        mount._set_carrier_upstream = carrier_config

        mount.install()
        app.read_namespaced_deployment.assert_called_once()
        core_v1_api.patch_namespaced_pod.assert_called_once()
        args = core_v1_api.patch_namespaced_pod.call_args
        self.assertEqual(
            args[1]["body"].spec.containers[0].image, "quay.io/gefyra/carrier2:latest"
        )

        mount.uninstall()
        app.patch_namespaced_deployment.assert_called_once()
        call_args = app.patch_namespaced_deployment.call_args
        body: V1Deployment = call_args[1]["body"]

        assert body.spec.template.metadata.annotations[
            "kubectl.kubernetes.io/restartedAt"
        ]

    @patch.multiple(
        "gefyra.bridge_mount.duplicate",
        app=DEFAULT,
        core_v1_api=DEFAULT,
        custom_object_api=DEFAULT,
    )
    def test_duplicate_already_exists_patches(
        self, app, core_v1_api, custom_object_api
    ):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        app.read_namespaced_deployment.return_value = NginxDeploymentFactory()
        pod = NginxPodFactory()
        core_v1_api.read_namespaced_pod_status.return_value = pod
        core_v1_api.list_namespaced_pod.return_value = V1PodListFactory(items=[pod])
        custom_object_api.get_namespaced_custom_object.return_value = {
            "target": "nginx-deployment",
        }
        from gefyra.bridge_mount import duplicate as duplicate_mod

        app.create_namespaced_deployment.side_effect = duplicate_mod.ApiException(
            status=409
        )
        app.patch_namespaced_deployment.return_value = True
        core_v1_api.create_namespaced_service.side_effect = duplicate_mod.ApiException(
            status=409
        )
        core_v1_api.patch_namespaced_service.return_value = True

        mount = DuplicateBridgeMount(
            name="test",
            configuration=OperatorConfiguration(),
            target_namespace="default",
            target="nginx",
            target_container="nginx",
            logger=logger,
        )
        mount.prepare()
        app.patch_namespaced_deployment.assert_called_once()
        core_v1_api.patch_namespaced_service.assert_called_once()

    @patch.multiple(
        "gefyra.bridge_mount.duplicate",
        core_v1_api=DEFAULT,
    )
    def test_carrier_upstream(self, core_v1_api):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        mount = DuplicateBridgeMount(
            name="test",
            configuration=OperatorConfiguration(),
            target_namespace="default",
            target="nginx",
            target_container="nginx",
            logger=logger,
        )

        core_v1_api.read_namespaced_service.return_value = V1ServiceFactory()

        # config creation works
        probe: V1Probe = V1ProbeFactory()
        carrier_config = mount._set_carrier_upstream(
            upstream_ports=[8080], probes=[probe]
        )

        assert carrier_config.clusterUpstream == [
            "nginx-service.default.svc.cluster.local:80"
        ]
        assert carrier_config.port == 8080
        assert carrier_config.probes.httpGet[0] == probe.http_get.port
