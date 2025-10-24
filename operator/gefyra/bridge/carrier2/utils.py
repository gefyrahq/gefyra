from typing import List
import time
import logging
from ssl import SSLEOFError

from kopf import TemporaryError
import kubernetes as k8s
from websocket import WebSocketConnectionClosedException

core_v1_api = k8s.client.CoreV1Api()

logger = logging.getLogger(__name__)


def stream_exec_retries(
    name: str, namespace: str, container: str, commands: List[str], retries: int = 30
):
    from kubernetes.client.rest import ApiException

    while retries > 0:
        try:
            return stream_exec(name, namespace, container, commands)
        except (ApiException, SSLEOFError) as e:
            logger.error(
                f"Failed to exec commands on pod {name} in namespace {namespace} with container {container}: {e}"
            )
            retries -= 1
            time.sleep(1)
            continue
        except WebSocketConnectionClosedException:
            raise Exception(
                f"Failed to exec commands with {retries} retries due to closed connection"
            )
    raise TemporaryError(f"Failed to exec commands with {retries} retries", delay=10)


def stream_exec(name: str, namespace: str, container: str, commands: List[str]):
    from kubernetes.stream import stream

    logger.info(
        f"Executing commands on pod {name} in namespace {namespace} with container {container}"
    )

    exec_command = ["busybox", "sh"]
    resp = stream(
        core_v1_api.connect_get_namespaced_pod_exec,
        name,
        namespace,
        command=exec_command,
        container=container,
        stderr=True,
        stdin=True,
        stdout=True,
        tty=False,
        _preload_content=False,
    )
    temp_commands = commands[:]
    last_ouput = None
    while resp.is_open():
        resp.update(timeout=5)
        if resp.peek_stdout():
            last_ouput = resp.read_stdout()
            logger.debug(f"[carrier2] {last_ouput}")
        if resp.peek_stderr():
            last_ouput = resp.read_stderr()
            logger.debug(f"[carrier2] {last_ouput}")
            continue
        if temp_commands:
            c = temp_commands.pop(0)
            logger.debug(f"Sending command: {c}")
            resp.write_stdin(c + "\n")
            time.sleep(0.5)
        else:
            break
        logger.debug(f"Last output: {last_ouput}")

    resp.close()
    return last_ouput


def read_carrier2_config(core_api, name: str, namespace: str) -> List[str]:
    from kubernetes.stream import stream

    exec_command = ["busybox", "sh"]
    resp = stream(
        core_api.connect_get_namespaced_pod_exec,
        name,
        namespace,
        command=exec_command,
        stderr=True,
        stdin=True,
        stdout=True,
        tty=False,
        _preload_content=False,
    )

    commands = []
    commands.append("cat /tmp/config.yaml \n")
    res = []
    while resp.is_open():
        resp.update(timeout=1)
        if resp.peek_stdout():
            res.append(resp.read_stdout())
        if resp.peek_stderr():
            res.append(resp.read_stdout())

        if commands:
            c = commands.pop(0)
            resp.write_stdin(c)
        else:
            break

    resp.close()
    return res
