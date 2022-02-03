import base64
import collections
from typing import Dict

import kubernetes as k8s

from gefyra.configuration import configuration


def create_wireguard_connection_secret(data: Dict) -> k8s.client.V1Secret:
    # values must be base64 encoded
    def enc_values(u):
        n = {}
        for k, v in u.items():
            if isinstance(v, collections.abc.Mapping):
                n[k] = enc_values(v)
            else:
                n[k] = (base64.b64encode(v.encode("utf-8"))).decode("utf-8")
        return n

    secret = k8s.client.V1Secret(
        api_version="v1",
        metadata=k8s.client.V1ObjectMeta(
            name="gefyra-cargo-connection", namespace=configuration.NAMESPACE
        ),
        data=enc_values(data),
        type="Opaque",
    )
    return secret
