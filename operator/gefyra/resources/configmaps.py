import random
import string

import kubernetes as k8s

from gefyra.configuration import configuration

PROXY_ROUTES = dict()
PORT_RANGE = [i for i in range(10000, 10101)]


def create_stowaway_proxyroute_configmap() -> k8s.client.V1ConfigMap:
    global PROXY_ROUTES
    configmap = k8s.client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        data=PROXY_ROUTES,
        metadata=k8s.client.V1ObjectMeta(name=configuration.STOWAWAY_PROXYROUTE_CONFIGMAPNAME)
    )
    return configmap


def add_route(to_ip: str, to_port: str) -> k8s.client.V1ConfigMap:
    global PROXY_ROUTES
    global PORT_RANGE
    port = random.choice(PORT_RANGE)
    PORT_RANGE.remove(port)
    PROXY_ROUTES[f"{''.join(random.choices(string.ascii_lowercase, k=10))}"] = f"{to_ip}:{to_port},{port}"
    return create_stowaway_proxyroute_configmap()


def remove_route(to_ip: str, to_port: int) -> k8s.client.V1ConfigMap:
    global PROXY_ROUTES
    global PORT_RANGE
    for name, route in PROXY_ROUTES.items():
        destinantion, port = route.split(",")
        if f"{to_ip}:{to_port}" == destinantion:
            PORT_RANGE.append(int(port))
    PROXY_ROUTES.pop(name)
    return create_stowaway_proxyroute_configmap()
