from unittest import TestCase
from unittest.mock import DEFAULT, MagicMock, patch

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
    V1ContainerPort,
    V1OwnerReference,
    V1PodStatus,
    V1PodCondition,
    V1ContainerStatus,
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

        app.read_namespaced_deployment.return_value = V1Deployment(
            metadata=V1ObjectMeta(
                name="nginx",
                labels={"app": "nginx"},
            ),
            spec=V1DeploymentSpec(
                selector=V1LabelSelector(match_labels={"app": "nginx"}),
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(labels={"app": "nginx"}),
                    spec=V1PodSpec(
                        containers=[
                            V1Container(
                                name="nginx",
                                image="nginx",
                                ports=[
                                    V1ContainerPort(
                                        container_port=80,
                                    )
                                ],
                            )
                        ]
                    ),
                ),
            ),
        )
        status = V1PodStatus(
            phase="Running",
            conditions=[
                V1PodCondition(
                    type="Ready",
                    status="True",
                )
            ],
            container_statuses=[
                V1ContainerStatus(
                    name="nginx",
                    image="nginx:latest",
                    image_id="docker://nginx:latest",
                    ready=True,
                    restart_count=1,
                )
            ],
        )
        pod = V1Pod(
            status=status,
            metadata=V1ObjectMeta(
                name="nginx-123",
                labels={"app": "nginx"},
                owner_references=[
                    V1OwnerReference(
                        api_version="apps/v1",
                        kind="Deployment",
                        name="nginx",
                        uid="12345678-1234-1234-1234-123456789012",
                    )
                ],
            ),
            spec=V1PodSpec(
                containers=[
                    V1Container(
                        name="nginx",
                        image="nginx",
                        ports=[
                            V1ContainerPort(
                                container_port=80,
                            )
                        ],
                    )
                ],
            ),
        )
        core_v1_api.read_namespaced_pod_status.return_value = pod
        core_v1_api.list_namespaced_pod.return_value = V1PodList(items=[pod])
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
