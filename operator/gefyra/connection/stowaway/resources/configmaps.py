import kubernetes as k8s
from gefyra.configuration import configuration

PORT_RANGE = [i for i in range(10000, 20000)]


def create_stowaway_proxyroute_configmap() -> k8s.client.V1ConfigMap:
    configmap = k8s.client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        data={},
        metadata=k8s.client.V1ObjectMeta(
            name=configuration.STOWAWAY_PROXYROUTE_CONFIGMAPNAME,
            namespace=configuration.NAMESPACE,
            labels={"gefyra.dev/app": "stowaway", "gefyra.dev/role": "proxyroute"},
        ),
    )
    return configmap


def create_stowaway_configmap(max_connection_age: int = -1) -> k8s.client.V1ConfigMap:
    configmap = k8s.client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        data={
            "PEERS": "0",
            "SERVERPORT": str(configuration.WIREGUARD_EXT_PORT),
            "PUID": configuration.STOWAWAY_PUID,
            "PGID": configuration.STOWAWAY_PGID,
            "PEERDNS": configuration.STOWAWAY_PEER_DNS,
            "INTERNAL_SUBNET": configuration.STOWAWAY_INTERNAL_SUBNET,
            "DEFAULT_MAX_CONNECTION_AGE": str(max_connection_age),
            "LOG_CONFS": "false",
        },
        metadata=k8s.client.V1ObjectMeta(
            name=configuration.STOWAWAY_CONFIGMAPNAME,
            namespace=configuration.NAMESPACE,
            labels={"gefyra.dev/app": "stowaway", "gefyra.dev/role": "connection"},
        ),
    )
    return configmap
