import kubernetes as k8s

from gefyra.configuration import configuration


def create_stowaway_nodeport_service(stowaway_deployment: k8s.client.V1Deployment):

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
        metadata=k8s.client.V1ObjectMeta(name="gefyra-stowaway-wireguard"),
        spec=spec,
    )

    return service
