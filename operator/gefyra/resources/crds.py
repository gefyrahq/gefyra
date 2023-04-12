import kubernetes as k8s

from gefyra.configuration import configuration


def create_interceptrequest_definition() -> k8s.client.V1CustomResourceDefinition:
    schema_props = k8s.client.V1JSONSchemaProps(
        type="object",
        properties={
            "established": k8s.client.V1JSONSchemaProps(type="boolean", default=False),
            "destinationIP": k8s.client.V1JSONSchemaProps(type="string"),
            "targetPod": k8s.client.V1JSONSchemaProps(
                type="string"
            ),  # target a specific Pod for intercept
            "targetContainer": k8s.client.V1JSONSchemaProps(type="string"),
            "targetNamespace": k8s.client.V1JSONSchemaProps(type="string"),
            "portMappings": k8s.client.V1JSONSchemaProps(
                type="array",
                default=[],
                items=k8s.client.V1JSONSchemaProps(type="string"),
            ),
            "syncDownDirectories": k8s.client.V1JSONSchemaProps(
                type="array",
                default=[],
                items=k8s.client.V1JSONSchemaProps(type="string"),
            ),
            "carrierOriginalConfig": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),  # object to store information for reset of target Pod
            "handleProbes": k8s.client.V1JSONSchemaProps(type="boolean", default=False),
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


def create_gefyraclient_definition() -> k8s.client.V1CustomResourceDefinition:
    schema_props = k8s.client.V1JSONSchemaProps(
        type="object",
        properties={
            # the Gefyra connection provider for this client
            "provider": k8s.client.V1JSONSchemaProps(type="string", enum=["stowaway"]),
            "providerParameter": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            # the native configuration of this connection provider for this client
            "providerConfig": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            # the name of the ServiceAccount to use for this client
            "serviceAccountName": k8s.client.V1JSONSchemaProps(type="string"),
            # the ServiceAccount token to use for this client
            "serviceAccountToken": k8s.client.V1JSONSchemaProps(type="string"),
            # a generated kubeconfig using the ServiceAccount token for this client
            "kubeconfig": k8s.client.V1JSONSchemaProps(type="string"),
            # datetime when this client is to be removed from the cluster
            "sunset": k8s.client.V1JSONSchemaProps(type="string"),
            # datetime when this client was last contacted
            "lastClientContact": k8s.client.V1JSONSchemaProps(type="string"),
            "state": k8s.client.V1JSONSchemaProps(type="string", default="REQUESTED"),
            "stateTransitions": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "status": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
        },
    )

    def_spec = k8s.client.V1CustomResourceDefinitionSpec(
        group="gefyra.dev",
        names=k8s.client.V1CustomResourceDefinitionNames(
            kind="gefyraclient",
            plural="gefyraclients",
            short_names=["gclients", "gclient"],
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
            name="gefyraclients.gefyra.dev",
            namespace=configuration.NAMESPACE,
            finalizers=[],
        ),
    )
    return crd
