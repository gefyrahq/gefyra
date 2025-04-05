import kubernetes as k8s
from kubernetes.client import V1Probe, V1HTTPGetAction

from gefyra.configuration import OperatorConfiguration


def create_stowaway_statefulset(
    labels: dict[str, str], configuration: OperatorConfiguration
) -> k8s.client.V1StatefulSet:
    container = k8s.client.V1Container(
        name="stowaway",
        image=f"{configuration.STOWAWAY_IMAGE}:{configuration.STOWAWAY_TAG}",
        image_pull_policy=configuration.STOWAWAY_IMAGE_PULLPOLICY,
        # Wireguard default port 51820 will be mapped by the nodeport service
        ports=[
            k8s.client.V1ContainerPort(container_port=51820, protocol="UDP"),
            k8s.client.V1ContainerPort(container_port=51822, protocol="TCP"),
        ],
        resources=k8s.client.V1ResourceRequirements(
            requests={"cpu": "0.1", "memory": "100Mi"},
            limits={"cpu": "0.75", "memory": "500Mi"},
        ),
        startup_probe=V1Probe(
            http_get=V1HTTPGetAction(
                port=51822,
            ),
            period_seconds=1,
            initial_delay_seconds=5,
        ),
        readiness_probe=V1Probe(
            http_get=V1HTTPGetAction(
                port=51822,
            ),
            period_seconds=1,
            initial_delay_seconds=5,
        ),
        liveness_probe=V1Probe(
            http_get=V1HTTPGetAction(
                port=51822,
            ),
            period_seconds=1,
            initial_delay_seconds=5,
        ),
        env_from=[
            k8s.client.V1EnvFromSource(
                config_map_ref=k8s.client.V1ConfigMapEnvSource(
                    name=configuration.STOWAWAY_CONFIGMAPNAME
                )
            )
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
            k8s.client.V1VolumeMount(name="stowaway-config", mount_path="/config"),
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

    spec = k8s.client.V1StatefulSetSpec(
        replicas=1,
        service_name="gefyra-stowaway",
        template=template,
        selector={"matchLabels": labels},
        volume_claim_templates=[
            k8s.client.V1PersistentVolumeClaim(
                metadata=k8s.client.V1ObjectMeta(name="stowaway-config"),
                spec=k8s.client.V1PersistentVolumeClaimSpec(
                    access_modes=["ReadWriteOnce"],
                    resources=k8s.client.V1ResourceRequirements(
                        requests={"storage": f"{configuration.STOWAWAY_STORAGE}Mi"}
                    ),
                ),
            )
        ],
    )

    sts = k8s.client.V1StatefulSet(
        metadata=k8s.client.V1ObjectMeta(
            name="gefyra-stowaway", namespace=configuration.NAMESPACE, labels=labels
        ),
        spec=spec,
    )

    return sts
