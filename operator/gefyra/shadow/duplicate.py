import kubernetes as k8s

from gefyra.shadow.abstract import AbstractGefyraShadowProvider
from gefyra.configuration import OperatorConfiguration

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
custom_object_api = k8s.client.CustomObjectsApi()

# TODO smarter shadow names


class DuplicateShadow(AbstractGefyraShadowProvider):
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

    def _duplicate_deployment(self, deployment_name: str, namespace: str) -> None:
        deployment = app.read_namespaced_deployment(deployment_name, namespace)

        # Create a copy of the deployment
        new_deployment = deployment

        # Update labels to add -gefyra suffix
        labels = new_deployment.metadata.labels or {}
        for key in labels:
            labels[key] = f"{labels[key]}-gefyra"
        new_deployment.metadata.labels = labels
        new_deployment.metadata.resource_version = None
        new_deployment.metadata.uid = None
        new_deployment.metadata.name = f"{deployment_name}-gefyra"

        pod_labels = new_deployment.spec.template.metadata.labels or {}
        for key in pod_labels:
            pod_labels[key] = f"{pod_labels[key]}-gefyra"
        new_deployment.spec.template.metadata.labels = pod_labels

        match_labels = new_deployment.spec.selector.match_labels or {}
        for key in match_labels:
            match_labels[key] = f"{match_labels[key]}-gefyra"
        new_deployment.spec.selector.match_labels = match_labels

        # Create the new deployment
        app.create_namespaced_deployment(namespace, new_deployment)

    def _duplicate_service(self, service_name: str, namespace: str) -> None:

        # Get the original service
        service = app.read_namespaced_service(service_name, namespace)

        # Create a copy of the service
        new_service = service

        # Clean up the new_service object
        new_service.metadata.resource_version = None
        new_service.metadata.uid = None
        new_service.metadata.self_link = None
        new_service.metadata.creation_timestamp = None
        new_service.metadata.generation = None
        new_service.metadata.name = f"{service_name}-gefyra"
        new_service.spec.cluster_ip = None
        new_service.spec.cluster_i_ps = None

        # Update labels to add -gefyra suffix
        labels = new_service.metadata.labels or {}
        for key in labels:
            labels[key] = f"{labels[key]}-gefyra"
        new_service.metadata.labels = labels

        # Update selector labels
        pod_labels = new_service.spec.selector or {}
        for key in pod_labels:
            pod_labels[key] = f"{pod_labels[key]}-gefyra"
        new_service.spec.selector = pod_labels

        # Create the new service
        app.create_namespaced_service(namespace, new_service)

    def install(self, parameters=None):
        self._duplicate_deployment(parameters["deployment"], parameters["namespace"])
        self._duplicate_service(parameters["service"], parameters["namespace"])

    def uninstall(self):
        # TODO
        pass


class DuplicateBuilder:
    def __init__(self):
        self._instances = {}

    def __call__(
        self,
        configuration: OperatorConfiguration,
        target_namespace: str,
        target: str,
        target_container: str,
        logger,
        **_ignored,
    ):
        instance = DuplicateShadow(
            configuration=configuration,
            target_namespace=target_namespace,
            target=target,
            target_container=target_container,
            logger=logger,
        )
        return instance
