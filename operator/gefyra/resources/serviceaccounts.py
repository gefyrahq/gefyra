import kopf
import kubernetes as k8s

rbac_v1_api = k8s.client.RbacAuthorizationV1Api()
core_v1_api = k8s.client.CoreV1Api()


def handle_create_gefyraclient_serviceaccount(
    logger, name: str, namespace: str, client_name: str
) -> None:
    """
    It creates a service account, a role, and a role binding to allow
    the service account to work with GefyraClients
    :param logger: a logger object
    :param name: The name of the service account to create
    :type name: str
    :param namespace: The namespace to create the service account in
    :type namespace: str
    """
    try:
        role = rbac_v1_api.read_cluster_role(
            name="gefyra-client",
        )
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            role = rbac_v1_api.create_cluster_role(
                body=k8s.client.V1ClusterRole(
                    metadata=k8s.client.V1ObjectMeta(name="gefyra-client"),
                    rules=[
                        k8s.client.V1PolicyRule(
                            api_groups=["gefyra.dev"],
                            resources=["gefyraclients"],
                            verbs=["delete"],
                            resource_names=[client_name],
                        ),
                        k8s.client.V1PolicyRule(
                            api_groups=["gefyra.dev"],
                            resources=["gefyraclients"],
                            verbs=["list", "patch", "get"],
                        ),
                        k8s.client.V1PolicyRule(
                            api_groups=["gefyra.dev"],
                            resources=["gefyrabridges"],
                            verbs=["list", "get", "create", "patch", "delete", "watch"],
                        ),
                        k8s.client.V1PolicyRule(
                            api_groups=[""],
                            resources=["pods/exec", "pods/status"],
                            verbs=["create", "get"],
                        ),
                        k8s.client.V1PolicyRule(
                            api_groups=["", "apps"],
                            resources=[
                                "pods",
                                "deployments",
                                "statefulsets",
                                "replicasets",
                                "namespaces",
                            ],
                            verbs=["list", "get"],
                        ),
                        k8s.client.V1PolicyRule(
                            api_groups=[""],
                            resources=[
                                "namespaces",
                            ],
                            verbs=["delete"],
                            resource_names=["gefyra"],
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
        rbac_v1_api.create_cluster_role_binding(
            body=k8s.client.V1ClusterRoleBinding(
                metadata=k8s.client.V1ObjectMeta(
                    name=f"gefyra-rolebinding-{sa.metadata.name}"
                ),
                subjects=[
                    k8s.client.RbacV1Subject(
                        kind="ServiceAccount",
                        name=sa.metadata.name,
                        namespace=namespace,
                    )
                ],
                role_ref=k8s.client.V1RoleRef(
                    kind="ClusterRole",
                    name=role.metadata.name,
                    api_group="rbac.authorization.k8s.io",
                ),
            ),
        )
        logger.info(f"Created serviceaccount and permissions for GefyraClient: {name}")
    except k8s.client.exceptions.ApiException as e:
        if e.status != 409:
            raise e


def handle_delete_gefyraclient_serviceaccount(
    logger,
    name: str,
    namespace: str,
) -> None:
    """
    Deletes service account, role and role binding for a GefyraClient

    Args:
        logger (logging): The logger object
        name (str): Name of the service account
        namespace (str): Namespace of the service account

    Raises:
        e: Exception if the service account could not be deleted and the status code is not 404
    """
    try:
        sa = core_v1_api.read_namespaced_service_account(name=name, namespace=namespace)
        rbac_v1_api.delete_cluster_role_binding(
            name=f"gefyra-rolebinding-{sa.metadata.name}"
        )
        core_v1_api.delete_namespaced_service_account(name=name, namespace=namespace)
        logger.info(f"Deleted serviceaccount and permissions for GefyraClient: {name}")
    except k8s.client.exceptions.ApiException as e:
        logger.warning(f"Could not delete serviceaccount {name}: {e}")
        if e.status != 404:
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
