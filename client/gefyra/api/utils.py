import logging
import time
from typing import Iterable

logger = logging.getLogger(__name__)


def get_workload_type(workload_type_str: str):
    POD = ["pod", "po", "pods"]
    DEPLOYMENT = ["deploy", "deployment", "deployments"]
    STATEFULSET = ["statefulset", "sts", "statefulsets"]
    VALID_TYPES = POD + DEPLOYMENT + STATEFULSET

    if workload_type_str not in VALID_TYPES:
        raise RuntimeError(
            f"Unknown workload type {workload_type_str}\n"
            f'Valid workload types include: {", ".join(str(valid_type) for valid_type in VALID_TYPES)}'
        )

    if workload_type_str in POD:
        return "pod"
    elif workload_type_str in DEPLOYMENT:
        return "deployment"
    elif workload_type_str in STATEFULSET:
        return "statefulset"


def generate_env_dict_from_strings(env_vars: Iterable[str]) -> dict:
    return {k[0]: k[1] for k in [arg.split("=", 1) for arg in env_vars] if len(k) > 1}


def stopwatch(func):
    def wrapper(*args, **kwargs):
        tic = time.perf_counter()
        result = func(*args, **kwargs)
        toc = time.perf_counter()
        logger.debug(
            f"Operation time for '{func.__name__}(...)' was {(toc - tic)*1000:0.4f}ms"
        )
        return result

    return wrapper
