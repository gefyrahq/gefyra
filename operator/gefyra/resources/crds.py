import kubernetes as k8s

from gefyra.configuration import configuration

CONNECTION_PROVIDERS = ["stowaway"]
BRIDGE_PROVIDERS = ["carrier", "carrier2"]


def create_gefyrabridge_definition() -> k8s.client.V1CustomResourceDefinition:
    schema_props = k8s.client.V1JSONSchemaProps(
        type="object",
        properties={
            # the Gefyra bridge provider for this request
            "provider": k8s.client.V1JSONSchemaProps(
                type="string", enum=BRIDGE_PROVIDERS
            ),
            # provider specific parameters for this bridge
            # a carrier example: {"type": "stream"} to proxy all traffic on TCP level
            # to the destination (much like a nitro-speed global bridge)
            # another carrier example: {"type": "http", "url": "/api"} to proxy all
            # traffic on HTTP level to the destination
            # sync_down_directories
            "providerParameter": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            # the Gefyra connection provider to establish the routed
            # connection to a client
            "connectionProvider": k8s.client.V1JSONSchemaProps(
                type="string", enum=CONNECTION_PROVIDERS
            ),
            # the targets for this bridge / traffic sources
            "targetNamespace": k8s.client.V1JSONSchemaProps(type="string"),
            "target": k8s.client.V1JSONSchemaProps(
                type="string"
            ),  # target bridge mount to connect to
            "targetContainer": k8s.client.V1JSONSchemaProps(type="string"),
            # the traffic destinations for this bridge
            "client": k8s.client.V1JSONSchemaProps(type="string"),
            # the IP address of the local container running at that client
            "destinationIP": k8s.client.V1JSONSchemaProps(type="string"),
            # map the ports of the bridge to the target container, for
            # example: [80:8080] will forward port 80 of the source container to port
            # 8080 of the local container
            "portMappings": k8s.client.V1JSONSchemaProps(
                type="array",
                default=[],
                items=k8s.client.V1JSONSchemaProps(type="string"),
            ),
            # Service name + port of the corresponding client stowaway proxy
            "clusterEndpoint": k8s.client.V1JSONSchemaProps(type="string", default=""),
            # "syncDownDirectories": k8s.client.V1JSONSchemaProps(
            #     type="array",
            #     default=[],
            #     items=k8s.client.V1JSONSchemaProps(type="string"),
            # ),
            # datetime when this bridge is to be removed from the cluster
            "sunset": k8s.client.V1JSONSchemaProps(type="string"),
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
            kind="gefyrabridge",
            plural="gefyrabridges",
            short_names=["gbridge", "gbridges"],
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
            name="gefyrabridges.gefyra.dev",
            namespace=configuration.NAMESPACE,
            finalizers=[],
        ),
    )
    return crd


def create_gefyraclient_definition() -> k8s.client.V1CustomResourceDefinition:
    schema_props = k8s.client.V1JSONSchemaProps(
        type="object",
        required=["provider"],
        properties={
            # the Gefyra connection provider for this client
            "provider": k8s.client.V1JSONSchemaProps(
                type="string", enum=CONNECTION_PROVIDERS
            ),
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
            "serviceAccountData": k8s.client.V1JSONSchemaProps(
                type="object",
                properties={
                    "token": k8s.client.V1JSONSchemaProps(type="string"),
                    "ca.crt": k8s.client.V1JSONSchemaProps(type="string"),
                    "namespace": k8s.client.V1JSONSchemaProps(type="string"),
                },
            ),
            # datetime when this client is to be removed from the cluster
            "sunset": k8s.client.V1JSONSchemaProps(type="string"),
            # time after which the connection is automatically closed
            "maxConnectionAge": k8s.client.V1JSONSchemaProps(type="integer"),
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


def create_bridge_mount_definition() -> k8s.client.V1CustomResourceDefinition:
    schema_props = k8s.client.V1JSONSchemaProps(
        type="object",
        properties={
            # the targets for this bridge / traffic sources
            "targetNamespace": k8s.client.V1JSONSchemaProps(type="string"),
            "target": k8s.client.V1JSONSchemaProps(
                type="string"
            ),  # target workload to intercept
            "targetContainer": k8s.client.V1JSONSchemaProps(type="string"),
            "provider": k8s.client.V1JSONSchemaProps(type="string"),
            "providerParameter": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "sunset": k8s.client.V1JSONSchemaProps(type="string"),
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
            kind="gefyrabridgemount",
            plural="gefyrabridgemounts",
            short_names=["gbridgemount", "gbridgemounts"],
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
            name="gefyrabridgemounts.gefyra.dev",
            namespace=configuration.NAMESPACE,
            finalizers=[],
        ),
    )
    return crd
