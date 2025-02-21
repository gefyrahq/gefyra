from unittest import TestCase

from kubernetes.client import (
    V1Deployment,
    V1DeploymentSpec,
    V1ObjectMeta,
    V1LabelSelector,
    V1PodTemplateSpec,
)

from gefyra.bridgemount.duplicate import DuplicateBridgeMount


class TestBridgeMountObject(TestCase):
    def test_bridge_mount_label_duplication(self):
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
