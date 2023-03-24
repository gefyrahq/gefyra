import kubernetes as k8s
from kubernetes.client import V1Probe, V1ExecAction

from gefyra.configuration import configuration





def create_stowaway_deployment(labels: dict[str, str]) -> k8s.client.V1Deployment:
    container = k8s.client.V1Container(
        name="stowaway",
        image=f"{configuration.STOWAWAY_IMAGE}:{configuration.STOWAWAY_TAG}",
        image_pull_policy=configuration.STOWAWAY_IMAGE_PULLPOLICY,
        # Wireguard default port 51820 will be mapped by the nodeport service
        ports=[k8s.client.V1ContainerPort(container_port=51820, protocol="UDP")],
        resources=k8s.client.V1ResourceRequirements(
            requests={"cpu": "0.1", "memory": "100Mi"},
            limits={"cpu": "0.75", "memory": "500Mi"},
        ),
        readiness_probe=V1Probe(
            _exec=V1ExecAction(
                command=["cat", "/config/peer1/peer1.conf"],
            ),
            period_seconds=1,
            initial_delay_seconds=1,
        ),
        env=[
            k8s.client.V1EnvVar(name="PEERS", value="1"),
            k8s.client.V1EnvVar(
                name="SERVERPORT", value=str(configuration.WIREGUARD_EXT_PORT)
            ),
            k8s.client.V1EnvVar(name="PUID", value=configuration.STOWAWAY_PUID),
            k8s.client.V1EnvVar(name="PGID", value=configuration.STOWAWAY_PGID),
            k8s.client.V1EnvVar(name="PEERDNS", value=configuration.STOWAWAY_PEER_DNS),
            k8s.client.V1EnvVar(
                name="INTERNAL_SUBNET", value=configuration.STOWAWAY_INTERNAL_SUBNET
            ),
            k8s.client.V1EnvVar(
                name="SERVER_ALLOWEDIPS_PEER_1", value=configuration.GEFYRA_PEER_SUBNET
            ),
        ],
        security_context=k8s.client.V1SecurityContext(
            privileged=True,
            capabilities=k8s.client.V1Capabilities(add=["NET_ADMIN", "SYS_MODULE"]),
        ),
        volume_mounts=[
            k8s.client.V1VolumeMount(
                name="proxyroutes", mount_path="/stowaway/proxyroutes"
            ),
            k8s.client.V1VolumeMount(name="host-libs", mount_path="/lib/modules"),
        ],
    )

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels=labels),
        spec=k8s.client.V1PodSpec(
            service_account_name="gefyra-stowaway",
            containers=[container],
            volumes=[
                k8s.client.V1Volume(
                    name="proxyroutes",
                    config_map=k8s.client.V1ConfigMapVolumeSource(
                        name=configuration.STOWAWAY_PROXYROUTE_CONFIGMAPNAME
                    ),
                ),
                k8s.client.V1Volume(
                    name="host-libs",
                    host_path=k8s.client.V1HostPathVolumeSource(
                        path="/lib/modules", type="Directory"
                    ),
                ),
            ],
        ),
    )

    spec = k8s.client.V1DeploymentSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": labels},
    )

    deployment = k8s.client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=k8s.client.V1ObjectMeta(
            name="gefyra-stowaway", namespace=configuration.NAMESPACE, labels=labels
        ),
        spec=spec,
    )

    return deployment
