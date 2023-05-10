import kubernetes as k8s

from gefyra.configuration import configuration

RSYNC_SERVICE_PORT = 10873


def create_stowaway_nodeport_service(
    stowaway_deployment: k8s.client.V1Deployment,
) -> k8s.client.V1Service:
    spec = k8s.client.V1ServiceSpec(
        type="NodePort",
        selector=stowaway_deployment.spec.template.metadata.labels,
        ports=[
            k8s.client.V1ServicePort(
                protocol="UDP",
                name="gefyra-wireguard",
                node_port=configuration.WIREGUARD_EXT_PORT,
                target_port=51820,
                port=51820,
            )
        ],
    )

    service = k8s.client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=k8s.client.V1ObjectMeta(
            name="gefyra-stowaway-wireguard",
            namespace=stowaway_deployment.metadata.namespace,
            labels={"gefyra.dev/app": "stowaway"},
        ),
        spec=spec,
    )

    return service


def create_stowaway_proxy_service(
    stowaway_deployment: k8s.client.V1Deployment, port: int, client_id: str = "unknown"
) -> k8s.client.V1Service:
    spec = k8s.client.V1ServiceSpec(
        type="ClusterIP",
        selector=stowaway_deployment.spec.template.metadata.labels,
        cluster_ip="None",  # this is a headless service
        ports=[
            k8s.client.V1ServicePort(
                name=str(port),
                target_port=port,
                port=port,
            )
        ],
    )

    service = k8s.client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=k8s.client.V1ObjectMeta(
            name=f"gefyra-stowaway-proxy-{port}",
            namespace=stowaway_deployment.metadata.namespace,
            labels={
                "gefyra.dev/app": "stowaway",
                "gefyra.dev/role": "proxy",
                "gefyra.dev/proxy-port": str(port),
                "gefyra.dev/client-id": client_id,
            },
        ),
        spec=spec,
    )

    return service


def create_stowaway_rsync_service(
    stowaway_deployment: k8s.client.V1Deployment,
) -> k8s.client.V1Service:
    spec = k8s.client.V1ServiceSpec(
        type="ClusterIP",
        selector=stowaway_deployment.spec.template.metadata.labels,
        cluster_ip="None",  # this is a headless service
        ports=[
            k8s.client.V1ServicePort(
                name=str(RSYNC_SERVICE_PORT),
                target_port=RSYNC_SERVICE_PORT,
                port=RSYNC_SERVICE_PORT,
            )
        ],
    )

    service = k8s.client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=k8s.client.V1ObjectMeta(
            name="gefyra-stowaway-rsync",
            namespace=stowaway_deployment.metadata.namespace,
            labels={"gefyra.dev/app": "stowaway"},
        ),
        spec=spec,
    )

    return service
