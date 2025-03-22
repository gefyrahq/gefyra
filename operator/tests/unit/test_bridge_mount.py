from unittest import TestCase
from unittest.mock import DEFAULT, patch

import logging

from kubernetes.client import (
    V1Deployment,
    V1DeploymentSpec,
    V1ObjectMeta,
    V1LabelSelector,
    V1PodTemplateSpec,
    V1Pod,
    V1PodList,
    V1PodSpec,
    V1Container,
)

from gefyra.configuration import OperatorConfiguration

logger = logging.getLogger(__name__)


class TestBridgeMountObject(TestCase):
    def test_bridge_mount_label_duplication(self):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        mount = DuplicateBridgeMount(
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
            configuration=None,
            target_namespace="default",
            target="nginx",
            target_container="nginx",
            logger=None,
        )

        deployment = V1Deployment()
        deployment.metadata = V1ObjectMeta(
            name="nginx",
            labels={"app": "nginx"},
        )
        deployment.spec = V1DeploymentSpec(
            selector=V1LabelSelector(match_labels={"app": "nginx"}),
            template=V1PodTemplateSpec(
                metadata=V1ObjectMeta(labels={"app": "nginx"}),
            ),
        )

        new_deployment = mount._clone_deployment_structure(deployment)
        self.assertEqual(new_deployment.metadata.name, "nginx-gefyra")
        self.assertEqual(new_deployment.metadata.labels, {"app": "nginx-gefyra"})
        self.assertEqual(
            new_deployment.spec.selector.match_labels, {"app": "nginx-gefyra"}
        )
        self.assertEqual(
            new_deployment.spec.template.metadata.labels,
            {"app": "nginx-gefyra"},
        )

    def test_cleaning_annotations(self):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        mount = DuplicateBridgeMount(
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

    @patch.multiple("gefyra.bridge_mount.duplicate", app=DEFAULT, core_v1_api=DEFAULT)
    def test_carrier_patch(self, app, core_v1_api):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        app.read_namespaced_deployment.return_value = V1Deployment(
            metadata=V1ObjectMeta(
                name="nginx",
                labels={"app": "nginx"},
            ),
            spec=V1DeploymentSpec(
                selector=V1LabelSelector(match_labels={"app": "nginx"}),
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(labels={"app": "nginx"}),
                ),
            ),
        )
        core_v1_api.list_namespaced_pod.return_value = V1PodList(
            items=[
                V1Pod(
                    metadata=V1ObjectMeta(
                        name="nginx-123",
                        labels={"app": "nginx"},
                    ),
                    spec=V1PodSpec(
                        containers=[
                            V1Container(
                                name="nginx",
                                image="nginx",
                            )
                        ],
                    ),
                )
            ]
        )
        mount = DuplicateBridgeMount(
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

        mount.install()
        app.read_namespaced_deployment.assert_called_once()
        core_v1_api.patch_namespaced_pod.assert_called_once()
        args = core_v1_api.patch_namespaced_pod.call_args
        self.assertEqual(
            args[1]["body"].spec.containers[0].image, "quay.io/gefyra/carrier2:latest"
        )
