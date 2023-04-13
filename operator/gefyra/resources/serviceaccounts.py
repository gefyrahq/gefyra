import kopf
import kubernetes as k8s

rbac_v1_api = k8s.client.RbacAuthorizationV1Api()
core_v1_api = k8s.client.CoreV1Api()


def handle_create_gefyraclient_serviceaccount(
    logger, name: str, namespace: str
) -> None:
    """
    It creates a service account, a role, and a role binding to allow the service account to work with GefyraClients
    :param logger: a logger object
    :param name: The name of the service account to create
    :type name: str
    :param namespace: The namespace to create the service account in
    :type namespace: str
    """
    try:
        role = rbac_v1_api.read_namespaced_role(
            namespace=namespace,
            name="gefyra-client",
        )
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            role = rbac_v1_api.create_namespaced_role(
                namespace=namespace,
                body=k8s.client.V1Role(
                    metadata=k8s.client.V1ObjectMeta(
                        name="gefyra-client", namespace=namespace
                    ),
                    rules=[
                        k8s.client.V1PolicyRule(
                            api_groups=["gefyra.dev/v1"],
                            resources=["gefyraclients"],
                            verbs=["*"],
                        ),
                    ],
                ),
            )
        else:
            raise e
    try:
        sa = core_v1_api.create_namespaced_service_account(
            namespace=namespace,
            body=k8s.client.V1ServiceAccount(
                metadata=k8s.client.V1ObjectMeta(name=name, namespace=namespace)
            ),
        )
        rbac_v1_api.create_namespaced_role_binding(
            namespace=namespace,
            body=k8s.client.V1RoleBinding(
                metadata=k8s.client.V1ObjectMeta(
                    name=f"gefyra-client-{sa.metadata.name}", namespace=namespace
                ),
                subjects=[
                    k8s.client.V1Subject(kind="ServiceAccount", name=sa.metadata.name)
                ],
                role_ref=k8s.client.V1RoleRef(
                    kind="Role",
                    name=role.metadata.name,
                    api_group="rbac.authorization.k8s.io",
                ),
            ),
        )
        logger.info(f"Created serviceaccount and permissions for GefyraClient: {name}")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


def get_serviceaccount_data(name: str, namespace: str) -> dict[str, str]:
    token_secret_name = f"{name}-token"
    try:
        token_secret = core_v1_api.read_namespaced_secret(
            name=token_secret_name, namespace=namespace
        )
        data = token_secret.data
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            try:
                token_secret = core_v1_api.create_namespaced_secret(
                    namespace=namespace,
                    body=k8s.client.V1Secret(
                        metadata=k8s.client.V1ObjectMeta(
                            name=token_secret_name,
                            namespace=namespace,
                            annotations={"kubernetes.io/service-account.name": name},
                        ),
                        type="kubernetes.io/service-account-token",
                    ),
                )
                data = token_secret.data
            except k8s.client.exceptions.ApiException as e:
                raise kopf.PermanentError(str(e))
        else:
            raise kopf.PermanentError(str(e))  # type: ignore
    if data is None:
        raise kopf.TemporaryError("Serviceaccount token not yet generated", delay=1)
    return data
