import kubernetes as k8s
from kubernetes.client import (
    V1Deployment,
)

from gefyra.bridge_mount.abstract import AbstractGefyraBridgeMountProvider
from gefyra.configuration import OperatorConfiguration

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
custom_object_api = k8s.client.CustomObjectsApi()


class DuplicateBridgeMount(AbstractGefyraBridgeMountProvider):
    provider_type = "duplicate"

    def __init__(
        self,
        configuration: OperatorConfiguration,
        target_namespace: str,
        target: str,
        target_container: str,
        logger,
    ) -> None:
        self.configuration = configuration
        self.namespace = target_namespace
        self.target = target
        self.container = target_container
        self.logger = logger

    def _get_duplication_labels(self, labels: dict[str, str]) -> dict[str, str]:
        duplication_labels = {}
        for key in labels:
            duplication_labels[key] = f"{labels[key]}-gefyra"
        return duplication_labels

    def _clean_annotations(self, annotations: dict[str, str]) -> dict[str, str]:
        ANNOTATION_FILTER = [
            "kubectl.kubernetes.io/last-applied-configuration",
            "deployment.kubernetes.io/revision",
        ]
        return {
            key: value
            for key, value in annotations.items()
            if key not in ANNOTATION_FILTER
        }

    def _clone_deployment_structure(self, deployment: V1Deployment) -> V1Deployment:
        new_deployment = deployment

        # Update labels to add -gefyra suffix
        labels = self._get_duplication_labels(new_deployment.metadata.labels or {})
        new_deployment.metadata.labels = labels
        new_deployment.metadata.resource_version = None
        new_deployment.metadata.uid = None
        new_deployment.metadata.name = f"{deployment.metadata.name}-gefyra"

        pod_labels = self._get_duplication_labels(
            new_deployment.spec.template.metadata.labels or {}
        )
        new_deployment.spec.template.metadata.labels = pod_labels

        match_labels = self._get_duplication_labels(
            new_deployment.spec.selector.match_labels or {}
        )
        new_deployment.spec.selector.match_labels = match_labels
        new_deployment.metadata.annotations = self._clean_annotations(
            new_deployment.metadata.annotations or {}
        )
        return new_deployment

    def _duplicate_deployment(self, deployment_name: str, namespace: str) -> None:
        deployment = app.read_namespaced_deployment(deployment_name, namespace)

        # Create a copy of the deployment
        new_deployment = self._clone_deployment_structure(deployment)

        # Create the new deployment
        app.create_namespaced_deployment(namespace, new_deployment)

    def prepare(self):
        self._duplicate_deployment(self.target, self.namespace)

    def install(self):
        # TODO extend to StatefulSet and Pods
        pass

    def ready(self):
        return super().ready()

    def validate(self, brige_request):
        return super().validate(brige_request)

    def uninstall_deployment(self, deployment_name: str, namespace: str) -> None:
        gefyra_deployment_name = f"{deployment_name}-gefyra"
        app.delete_namespaced_deployment(gefyra_deployment_name, namespace)

    def uninstall(self):
        self.uninstall_deployment(self.target, self.namespace)
