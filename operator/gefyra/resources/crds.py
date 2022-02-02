import kubernetes as k8s

from configuration import configuration


def create_interceptrequest_definition() -> k8s.client.V1CustomResourceDefinition:
    schema_props = k8s.client.V1JSONSchemaProps(
        type="object",
        properties={
            "established": k8s.client.V1JSONSchemaProps(type="boolean", default=False),
            "destinationIP": k8s.client.V1JSONSchemaProps(type="string"),
            "destinationPort": k8s.client.V1JSONSchemaProps(type="string"),
            "targetPod": k8s.client.V1JSONSchemaProps(
                type="string"
            ),  # target a specific Pod for intercept
            "targetContainer": k8s.client.V1JSONSchemaProps(type="string"),
            "targetNamespace": k8s.client.V1JSONSchemaProps(type="string"),
            "targetContainerPort": k8s.client.V1JSONSchemaProps(type="string"),
            "syncDownDirectories": k8s.client.V1JSONSchemaProps(
                type="array",
                default=[],
                items=k8s.client.V1JSONSchemaProps(type="string"),
            ),
            "carrierOriginalConfig": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),  # object to store information for reset of target Pod
        },
    )

    def_spec = k8s.client.V1CustomResourceDefinitionSpec(
        group="gefyra.dev",
        names=k8s.client.V1CustomResourceDefinitionNames(
            kind="InterceptRequest",
            plural="interceptrequests",
            short_names=["ireq"],
        ),
        scope="Namespaced",
        versions=[
            k8s.client.V1CustomResourceDefinitionVersion(
                name="v1",
                served=True,
                storage=True,
                schema=k8s.client.V1CustomResourceValidation(
                    open_apiv3_schema=schema_props
                ),
            )
        ],
    )

    crd = k8s.client.V1CustomResourceDefinition(
        api_version="apiextensions.k8s.io/v1",
        kind="CustomResourceDefinition",
        spec=def_spec,
        metadata=k8s.client.V1ObjectMeta(
            name="interceptrequests.gefyra.dev",
            namespace=configuration.NAMESPACE,
            finalizers=[],
        ),
    )
    return crd
