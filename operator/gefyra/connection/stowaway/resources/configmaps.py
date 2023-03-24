import kubernetes as k8s
from gefyra.configuration import configuration

PROXY_ROUTES = dict()
PORT_RANGE = [i for i in range(10000, 10020)]


def create_stowaway_proxyroute_configmap() -> k8s.client.V1ConfigMap:
    global PROXY_ROUTES
    configmap = k8s.client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        data=PROXY_ROUTES,
        metadata=k8s.client.V1ObjectMeta(
            name=configuration.STOWAWAY_PROXYROUTE_CONFIGMAPNAME,
            namespace=configuration.NAMESPACE,
        ),
    )
    return configmap
