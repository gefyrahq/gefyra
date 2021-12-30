import base64
import collections
import json
import os
import subprocess
from datetime import datetime

import docker
import kubernetes as k8s
from docker.models.containers import Container

CARGO_DOCKERFILE_LOCATION = os.getenv(
    "GEFYRA_CARGO_DOCKERFILE_LOCATION", "/tmp/DOCKERFILE.CARGO"
)
CARGO_IMAGE_NAME = os.getenv("GEFYRA_CARGO_IMAGE_NAME", "gefyra_cargo")
NETWORK_NAME = os.getenv("GEFYRA_NETWORK_NAME", "gefyra_bridge")

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
    tag = f"{CARGO_IMAGE_NAME}:{datetime.now().strftime('%Y%m%d%H%M%S')}"
    # TODO: I'm not sure about `path` here... This works if script is called from gefyra project dir (../..)
    image, build_logs = client.images.build(
        path="client/cli/cargo", rm=True, forcerm=True, buildargs=build_args, tag=tag
    )
    return image, build_logs


def get_container_ip(container: Container = None, container_id: str = None):
    assert container or container_id, "Either container or id must be specified!"

    # TODO handle exceptions
    if container:
        # we might need to reload attrs
        container.reload()
    else:
        container = client.containers.get(container_id)
    return container.attrs["NetworkSettings"]["Networks"][NETWORK_NAME]["IPAddress"]


async def change_container_default_route(events, container_id, ip_address):
    for event in events:
        event_dict = json.loads(event.decode("utf-8"))
        print(event_dict)
        if event_dict["status"] == "start":
            subprocess.call(["cli/cargo/route_setting.sh", container_id, ip_address])
            return True
