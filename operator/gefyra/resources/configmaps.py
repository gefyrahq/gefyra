import random
import string
from typing import Tuple

import kubernetes as k8s

from gefyra.configuration import configuration


def add_route(to_ip: str, to_port: str) -> Tuple[k8s.client.V1ConfigMap, int]:
    """
    Create a new pair of target IP/port and prxy port
    :param to_ip: the target IP address of the host in Gefyra's client network
    :param to_port: the target port
    :return: V1ConfigMap, selected port
    """
    global PROXY_ROUTES
    global PORT_RANGE
    port = random.choice(PORT_RANGE)
    PORT_RANGE.remove(port)
    PROXY_ROUTES[
        f"{''.join(random.choices(string.ascii_lowercase, k=10))}"
    ] = f"{to_ip}:{to_port},{port}"
    return create_stowaway_proxyroute_configmap(), port


def remove_route(to_ip: str, to_port: int) -> Tuple[k8s.client.V1ConfigMap, int]:
    global PROXY_ROUTES
    global PORT_RANGE
    target_port = None
    for name, route in PROXY_ROUTES.items():
        destinantion, port = route.split(",")
        if f"{to_ip}:{to_port}" == destinantion:
            PORT_RANGE.append(int(port))
            PROXY_ROUTES.pop(name)
            target_port = port
            break
    return create_stowaway_proxyroute_configmap(), target_port
