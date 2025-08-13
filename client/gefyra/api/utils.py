import logging
import socket
import time
from typing import Any, Dict, Iterable, TYPE_CHECKING, Tuple, Optional

from gefyra.exceptions import GefyraBridgeError

if TYPE_CHECKING:
    from gefyra.types import GefyraBridge

logger = logging.getLogger(__name__)


def is_port_free(port):
    """
    Check if a port is free on the current system.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def get_workload_type(workload_type_str: str):
    POD = ["pod", "po", "pods"]
    DEPLOYMENT = ["deploy", "deployment", "deployments"]
    STATEFULSET = ["statefulset", "sts", "statefulsets"]
    VALID_TYPES = POD + DEPLOYMENT + STATEFULSET

    if workload_type_str not in VALID_TYPES:
        raise RuntimeError(
            f"Unknown workload type {workload_type_str}\nValid workload types include:"
            f" {', '.join(str(valid_type) for valid_type in VALID_TYPES)}"
        )

    if workload_type_str in POD:
        return "pod"
    elif workload_type_str in DEPLOYMENT:
        return "deployment"
    elif workload_type_str in STATEFULSET:
        return "statefulset"


def generate_env_dict_from_strings(env_vars: Iterable[str]) -> dict:
    return {k[0]: k[1] for k in [arg.split("=", 1) for arg in env_vars] if len(k) > 1}


def wrap_bridge(bridge: Dict[Any, Any]) -> "GefyraBridge":
    from gefyra.types import GefyraBridge

    return GefyraBridge(
        provider=bridge["provider"],
        name=bridge["metadata"]["name"],
        client_id=bridge["client"],
        local_container_ip=bridge["destinationIP"],
        port_mappings=bridge["portMappings"] or [],
        target_container=bridge["targetContainer"],
        target_namespace=bridge["targetNamespace"],
        target=bridge["target"],
        state=bridge["state"],
    )


def stopwatch(func):
    def wrapper(*args, **kwargs):
        tic = time.perf_counter()
        result = func(*args, **kwargs)
        toc = time.perf_counter()
        logger.debug(
            f"Operation time for '{func.__name__}(...)' was {(toc - tic) * 1000:0.4f}ms"
        )
        return result

    return wrapper


def get_workload_information(target: str) -> Tuple[str, str, str]:
    try:
        _bits = list(filter(None, target.split("/")))
        workload_type, workload_name = _bits[0:2]
        container_name = _bits[2]
    except IndexError:
        raise GefyraBridgeError(
            "Invalid --target notation. Use"
            " <workload_type>/<workload_name>/<container_name>."
        ) from None
    return workload_type, workload_name, container_name


def _parse_k8s_cpu_to_cpu_quota(cpu: Optional[str]) -> Optional[int]:
    """
    Convert K8s CPU specifications into a Docker/CFS cpu_quota value (in µs), based on the default period of 100000 µs.
      "100m"  -> 100 * 100 = 10000
      "500m"  -> 500 * 100 = 50000
      "1"     -> 1 * 100000 = 100000
      "1.5"   -> 1.5 * 100000 = 150000
    """
    if not cpu:
        return None
    v = cpu.strip().lower()
    try:
        if v.endswith("m"):
            m = int(v[:-1])
            quota = m * 100  # (m/1000) * 100000
        else:
            cpus = float(v)
            quota = int(round(cpus * 100_000))
        if quota != 0 and quota < 1000:
            quota = 1000  # mind. 1 ms
        return quota
    except Exception as e:
        logger.debug(f"Failed parsing CPU quantity '{cpu}': {e}")
        return None



def _parse_k8s_mem_to_bytes(mem: Optional[str]) -> Optional[int]:
    if not mem:
        return None
    v = mem.strip()
    try:
        return int(v)  # already bytes
    except ValueError:
        pass
    units = {
        "ki": 1024,
        "mi": 1024**2,
        "gi": 1024**3,
        "ti": 1024**4,
        "k": 1000,
        "m": 1000**2,
        "g": 1000**3,
        "t": 1000**4,
    }
    lv = v.lower()
    for suf, fac in units.items():
        if lv.endswith(suf):
            try:
                num = float(v[: -len(suf)])
                return int(num * fac)
            except Exception:
                return None
    try:
        return int(float(v))
    except Exception as e:
        logger.debug(f"Failed parsing memory quantity '{mem}': {e}")
        return None
