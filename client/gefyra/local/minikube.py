import json
import logging
from pathlib import Path

logger = logging.getLogger("gefyra")

MINIKUBE_CONFIG = "~/.minikube/profiles/minikube/config.json"


def _read_minikube_config() -> dict:
    config_file = Path(MINIKUBE_CONFIG).expanduser()
    with open(config_file, "r") as f:
        data = json.load(f)
    return data


def _get_a_worker_ip(config: dict):
    nodes = config["Nodes"]
    for node in nodes:
        if node["Worker"]:
            return node["IP"]
    raise RuntimeError("This Minikube cluster does not have a worker node.")


def detect_minikube_config() -> dict:
    """
    Read the config for a local Minikube cluster from its configuration file and set Gefyra accordingly
    :return: a preped ClientConfiguration object
    """
    try:
        config = _read_minikube_config()
    except FileNotFoundError:
        raise RuntimeError(
            f"Could not find the Minikube configuration at {MINIKUBE_CONFIG}. Did you start Minikube?"
        )
    except Exception as e:
        raise RuntimeError(
            f"There was an error reading the Minikube configuration: {e}"
        )
    driver = config["Driver"]
    if driver == "docker":
        try:
            network_name = config["Network"] or "minikube"
        except KeyError:
            network_name = "minikube"
    elif driver in ["kvm", "kvm2", "virtualbox"]:
        network_name = None
    else:
        raise RuntimeError(
            f"Gefyra does not support Minikube with this driver {driver}"
        )

    endpoint = _get_a_worker_ip(config)
    logger.debug(
        f"Minikube setup with driver '{driver}' network '{network_name}' and endpoint '{endpoint}'"
    )

    configuration_parameters = {
        "network_name": network_name,
        "cargo_endpoint": f"{endpoint}:31820",
        "kube_context": "minikube",
    }
    return configuration_parameters
