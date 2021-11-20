import kubernetes as k8s

from gefyra.configuration import configuration


def create_stowaway_deployment(suffix: str = ""):

    container = k8s.client.V1Container(
        name="stowaway",
        image=f"{configuration.STOWAWY_IMAGE}:{configuration.STOWAWY_TAG}",
        # Wireguard default port 51820 will be mapped by the nodeport service
        ports=[k8s.client.V1ContainerPort(container_port=51820, protocol="UDP")],
        resources=k8s.client.V1ResourceRequirements(
            requests={"cpu": "0.1", "memory": "100Mi"},
            limits={"cpu": "0.75", "memory": "500Mi"},
        ),
        env=[
            k8s.client.V1EnvVar(name="PEERS", value="1"),
            k8s.client.V1EnvVar(name="SERVERPORT", value=str(configuration.WIREGUARD_EXT_PORT)),
            k8s.client.V1EnvVar(name="PUID", value=configuration.STOWAWAY_PUID),
            k8s.client.V1EnvVar(name="PGID", value=configuration.STOWAWAY_PGID),
            k8s.client.V1EnvVar(name="PEERDNS", value=configuration.STOWAWAY_PEER_DNS),
            k8s.client.V1EnvVar(name="INTERNAL_SUBNET", value=configuration.STOWAWAY_INTERNAL_SUBNET),
        ],
        security_context=k8s.client.V1SecurityContext(
            privileged=True,
            capabilities=k8s.client.V1Capabilities(
                add=["NET_ADMIN", "SYS_MODULE"]
            )
        )
    )

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels={"app": "stowaway"}),
        spec=k8s.client.V1PodSpec(containers=[container]),
    )

    spec = k8s.client.V1DeploymentSpec(
        replicas=1, template=template, selector={"matchLabels": {"app": "stowaway"}})

    deployment = k8s.client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=k8s.client.V1ObjectMeta(name="gefyra-stowaway"),
        spec=spec,
    )

    return deployment
