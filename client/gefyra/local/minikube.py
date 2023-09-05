import json
import logging
from pathlib import Path
from typing import Optional

from gefyra.exceptions import MinikubeError

logger = logging.getLogger("gefyra")

MINIKUBE_CONFIG = "~/.minikube/profiles/{profile}/config.json"


def _read_minikube_config(profile: Optional[str] = "minikube") -> dict:
    config_file = Path(MINIKUBE_CONFIG.format(profile=profile)).expanduser()
    with open(config_file, "r") as f:
        data = json.load(f)
    return data


def _get_a_worker_ip(config: dict):
    nodes = config["Nodes"]
    for node in nodes:
        if node["Worker"]:
            return node["IP"]
    raise RuntimeError("This Minikube cluster does not have a worker node.")


def detect_minikube_config(profile: Optional[str] = "minikube") -> dict:
    """
    Read the config for a local Minikube cluster from its configuration
    file and set Gefyra accordingly.
    :return: a preped ClientConfiguration object
    """
    try:
        config = _read_minikube_config(profile)
    except FileNotFoundError:
        raise MinikubeError(
            f"The minikube profile {profile} does not exist. Did you start"
            " Minikube? Please also review your profile with 'minikube profile list'"
            " and try again. Minikube profiles are case-sensitive."
        )
    except Exception as e:
        raise MinikubeError(
            f"There was an error reading the Minikube configuration: {e}"
        )
    driver = config["Driver"]
    if driver == "docker":
        try:
            network_name = config["Network"] or config["Name"]
        except KeyError:
            network_name = "minikube"
    elif driver in ["kvm", "kvm2", "virtualbox"]:
        network_name = None
    else:
        raise MinikubeError(
            f"Gefyra does not support Minikube with this driver {driver}"
        )

    endpoint = _get_a_worker_ip(config)
    logger.debug(
        f"Minikube setup with driver '{driver}' network '{network_name}' and endpoint"
        f" '{endpoint}'"
    )

    configuration_parameters = {
        "network_name": network_name,
        "cargo_endpoint_host": endpoint,
        "cargo_endpoint_port": "31820",
        "kube_context": config["Name"],
    }
    return configuration_parameters
