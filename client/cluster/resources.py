import kubernetes as k8s


def create_operator_serviceaccount(namespace: str) -> k8s.client.V1ServiceAccount:
    return k8s.client.V1ServiceAccount(
        metadata=k8s.client.V1ObjectMeta(
            # this name is referenced by Operator
            name="gefyra-operator",
            namespace=namespace,
        )
    )


def create_operator_clusterrole() -> k8s.client.V1ClusterRole:

    crd_rule = k8s.client.V1PolicyRule(
        api_groups=["apiextensions.k8s.io"],
        resources=["customresourcedefinitions"],
        verbs=["create", "patch", "delete", "list", "watch"],
    )
    kopf_rules = k8s.client.V1PolicyRule(
        api_groups=["kopf.dev"],
        resources=[
            "clusterkopfpeerings",
        ],
        verbs=[
            "create",
            "patch",
        ],
    )
    # this is potentially not needed for kopf in standalone mode
    # kopf_peering = k8s.client.V1PolicyRule(
    #     api_groups=[
    #         "admissionregistration.k8s.io/v1",
    #         "admissionregistration.k8s.io/v1beta1"
    #     ],
    #     resources=[
    #         "validatingwebhookconfigurations",
    #         "mutatingwebhookconfigurations"
    #     ],
    #     verbs=[
    #         "list",
    #         "watch",
    #         "patch",
    #         "get"
    #     ]
    # )
    misc_res_rule = k8s.client.V1PolicyRule(
        api_groups=["", "apps", "extensions", "events.k8s.io"],
        resources=[
            "namespaces",
            "configmaps",
            "secrets",
            "deployments",
            "services",
            "pods",
            "pods/exec",
            "events",
        ],
        verbs=["create", "patch", "update", "delete", "get", "list"],
    )
    ireq_rule = k8s.client.V1PolicyRule(
        api_groups=["gefyra.dev"], resources=["interceptrequests"], verbs=["*"]
    )

    clusterrole = k8s.client.V1ClusterRole(
        kind="ClusterRole",
        metadata=k8s.client.V1ObjectMeta(
            # this name is referenced by Operator
            name="gefyra-operator-role",
        ),
        rules=[
            crd_rule,
            kopf_rules,
            # kopf_peering,
            misc_res_rule,
            ireq_rule,
        ],
    )
    return clusterrole


def create_operator_clusterrolebinding(
    serviceaccount: k8s.client.V1ServiceAccount,
    clusterrole: k8s.client.V1ClusterRole,
    namespace: str,
) -> k8s.client.V1ClusterRoleBinding:
    return k8s.client.V1ClusterRoleBinding(
        metadata=k8s.client.V1ObjectMeta(
            # this name is referenced by Operator
            name="gefyra-operator-rolebinding",
        ),
        role_ref=k8s.client.V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            name=clusterrole.metadata.name,
            kind="ClusterRole",
        ),
        subjects=[
            k8s.client.V1Subject(
                kind="ServiceAccount",
                name=serviceaccount.metadata.name,
                namespace=namespace,
            )
        ],
    )


def create_operator_deployment(
    serviceaccount: k8s.client.V1ServiceAccount, namespace: str
) -> k8s.client.V1Deployment:

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels={"app": "gefyra-operator"}),
        spec=k8s.client.V1PodSpec(
            containers=[
                k8s.client.V1Container(
                    name="gefyra-operator",
                    image="quay.io/gefyra/operator:latest",
                )
            ],
            service_account_name=serviceaccount.metadata.name,
        ),
    )
    spec = k8s.client.V1DeploymentSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": {"app": "gefyra-operator"}},
    )
    deployment = k8s.client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=k8s.client.V1ObjectMeta(name="gefyra-operator", namespace=namespace),
        spec=spec,
    )

    return deployment
