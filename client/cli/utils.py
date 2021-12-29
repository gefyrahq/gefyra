import base64
import collections
import os
from datetime import datetime

import docker
import kubernetes as k8s

CARGO_DOCKERFILE_LOCATION = os.getenv(
    "GEFYRA_CARGO_DOCKERFILE_LOCATION", "/tmp/DOCKERFILE.CARGO"
)
CARGO_IMAGE_NAME = os.getenv("GEFYRA_CARGO_IMAGE_NAME", "gefyra_cargo")

k8s.config.load_kube_config()
core_api = k8s.client.CoreV1Api()
client = docker.from_env()
NAMESPACE = os.getenv("GEFYRA_NAMESPACE", "gefyra")


def decode_secret(u):
    n = {}
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            n[k] = decode_secret(v)
        else:
            n[k] = (base64.b64decode(v.encode("utf-8"))).decode("utf-8")
    return n


def get_cargo_connection_data():
    cargo_connection_secret = core_api.read_namespaced_secret(
        name="gefyra-cargo-connection", namespace=NAMESPACE
    )
    return decode_secret(cargo_connection_secret.data)


def build_cargo_image(
    wireguard_ip, private_key, dns, public_key, endpoint, allowed_ips
):
    build_args = {
        "ADDRESS": wireguard_ip,
        "PRIVATE_KEY": private_key,
        "DNS": dns,
        "PUBLIC_KEY": public_key,
        "ENDPOINT": endpoint,
        "ALLOWED_IPS": allowed_ips,
    }
    # we need to make the tag unique in order to support multiple cargo images, i.e. multiple bridge operations
    tag = f"{CARGO_IMAGE_NAME}:{datetime.now().strftime('%Y%m%d%H%M%S')}"
    image, build_logs = client.images.build(
        path="cargo", rm=True, forcerm=True, buildargs=build_args, tag=tag
    )
    return image, build_logs
