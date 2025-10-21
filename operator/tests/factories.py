import factory

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
    V1Probe,
    V1HTTPGetAction,
    V1Service,
    V1ServiceSpec,
    V1ServicePort,
)


class V1ObjectMetaFactory(factory.Factory):
    class Meta:
        model = V1ObjectMeta

    name = factory.Sequence(lambda n: f"test-object-{n}")
    labels = factory.Dict({"app": "nginx"})
    annotations = None
    namespace = "default"
    owner_references = None


class V1ContainerPortFactory(factory.Factory):
    class Meta:
        model = V1ContainerPort

    container_port = 80


class V1HTTPGetActionFactory(factory.Factory):
    class Meta:
        model = V1HTTPGetAction

    path = "/health"
    port = 8080


class V1ProbeFactory(factory.Factory):
    class Meta:
        model = V1Probe

    initial_delay_seconds = 5
    period_seconds = 10
    timeout_seconds = 1
    success_threshold = 1
    failure_threshold = 3
    http_get = factory.SubFactory(V1HTTPGetActionFactory)


class V1ServicePortFactory(factory.Factory):
    class Meta:
        model = V1ServicePort

    port = 80
    target_port = 80
    protocol = "TCP"


class V1ServiceSpecFactory(factory.Factory):
    class Meta:
        model = V1ServiceSpec

    selector = factory.Dict({"app": "nginx"})
    ports = factory.List([factory.SubFactory(V1ServicePortFactory)])
    type = "ClusterIP"


class V1ServiceFactory(factory.Factory):
    class Meta:
        model = V1Service

    metadata = factory.SubFactory(
        V1ObjectMetaFactory, name="nginx-service", labels={"app": "nginx"}
    )
    spec = factory.SubFactory(V1ServiceSpecFactory)


class V1ContainerFactory(factory.Factory):
    class Meta:
        model = V1Container

    name = "nginx"
    image = "nginx"
    ports = factory.List([factory.SubFactory(V1ContainerPortFactory)])


class V1PodSpecFactory(factory.Factory):
    class Meta:
        model = V1PodSpec

    containers = factory.List([factory.SubFactory(V1ContainerFactory)])


class V1LabelSelectorFactory(factory.Factory):
    class Meta:
        model = V1LabelSelector

    match_labels = factory.Dict({"app": "nginx"})


class V1PodTemplateSpecFactory(factory.Factory):
    class Meta:
        model = V1PodTemplateSpec

    metadata = factory.SubFactory(V1ObjectMetaFactory, name="", labels={"app": "nginx"})
    spec = factory.SubFactory(V1PodSpecFactory)


class V1DeploymentSpecFactory(factory.Factory):
    class Meta:
        model = V1DeploymentSpec

    selector = factory.SubFactory(V1LabelSelectorFactory)
    template = factory.SubFactory(V1PodTemplateSpecFactory)


class V1DeploymentFactory(factory.Factory):
    class Meta:
        model = V1Deployment

    metadata = factory.SubFactory(
        V1ObjectMetaFactory, name="nginx", labels={"app": "nginx"}
    )
    spec = factory.SubFactory(V1DeploymentSpecFactory)


class V1OwnerReferenceFactory(factory.Factory):
    class Meta:
        model = V1OwnerReference

    api_version = "apps/v1"
    kind = "Deployment"
    name = "nginx"
    uid = "12345678-1234-1234-1234-123456789012"


class V1PodConditionFactory(factory.Factory):
    class Meta:
        model = V1PodCondition

    type = "Ready"
    status = "True"


class V1ContainerStatusFactory(factory.Factory):
    class Meta:
        model = V1ContainerStatus

    name = "nginx"
    image = "nginx:latest"
    image_id = "docker://nginx:latest"
    ready = True
    restart_count = 1


class V1PodStatusFactory(factory.Factory):
    class Meta:
        model = V1PodStatus

    phase = "Running"
    conditions = factory.List([factory.SubFactory(V1PodConditionFactory)])
    container_statuses = factory.List([factory.SubFactory(V1ContainerStatusFactory)])


class V1PodFactory(factory.Factory):
    class Meta:
        model = V1Pod

    metadata = factory.SubFactory(
        V1ObjectMetaFactory, name="nginx-123", labels={"app": "nginx"}
    )
    spec = factory.SubFactory(V1PodSpecFactory)
    status = factory.SubFactory(V1PodStatusFactory)


class V1PodListFactory(factory.Factory):
    class Meta:
        model = V1PodList

    items = factory.List([])


class NginxDeploymentFactory(V1DeploymentFactory):
    metadata = factory.SubFactory(
        V1ObjectMetaFactory, name="nginx", labels={"app": "nginx"}
    )
    spec = factory.SubFactory(
        V1DeploymentSpecFactory,
        selector=factory.SubFactory(
            V1LabelSelectorFactory, match_labels={"app": "nginx"}
        ),
        template=factory.SubFactory(
            V1PodTemplateSpecFactory,
            metadata=factory.SubFactory(
                V1ObjectMetaFactory, name="", labels={"app": "nginx"}
            ),
            spec=factory.SubFactory(
                V1PodSpecFactory,
                containers=factory.List(
                    [
                        factory.SubFactory(
                            V1ContainerFactory, name="nginx", image="nginx"
                        )
                    ]
                ),
            ),
        ),
    )


class NginxPodFactory(V1PodFactory):
    metadata = factory.SubFactory(
        V1ObjectMetaFactory,
        name="nginx-123",
        labels={"app": "nginx"},
        owner_references=factory.List([factory.SubFactory(V1OwnerReferenceFactory)]),
    )
    spec = factory.SubFactory(
        V1PodSpecFactory,
        containers=factory.List(
            [factory.SubFactory(V1ContainerFactory, name="nginx", image="nginx")]
        ),
    )
    status = factory.SubFactory(V1PodStatusFactory)
