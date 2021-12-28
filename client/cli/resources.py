import os

import docker

CARGO_DOCKERFILE_LOCATION = os.getenv(
    "GEFYRA_CARGO_DOCKERFILE_LOCATION", "/tmp/DOCKERFILE.CARGO"
)
CARGO_IMAGE_TAG = os.getenv("GEFYRA_CARGO_IMAGE_TAG", "gefyra_cargo")

client = docker.from_env()


def build_cargo_image(wireguard_ip, private_key, dns, public_key, endpoint):
    build_args = {
        "ADDRESS": wireguard_ip,
        "PRIVATE_KEY": private_key,
        "DNS": dns,
        "PUBLIC_KEY": public_key,
        "ENDPOINT": endpoint,
    }
    client.images.build(
        path="cargo", rm=True, forcerm=True, buildargs=build_args, tag=CARGO_IMAGE_TAG
    )
