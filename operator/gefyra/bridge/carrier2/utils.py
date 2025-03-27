from typing import List
import time
import logging

import kubernetes as k8s
from websocket import WebSocketConnectionClosedException

core_v1_api = k8s.client.CoreV1Api()

logger = logging.getLogger(__name__)


def stream_exec_retries(
    name: str, namespace: str, commands: List[str], retries: int = 30
):
    from kubernetes.client.rest import ApiException

    while retries > 0:
        try:
            return stream_exec(name, namespace, commands)
        except ApiException:
            retries -= 1
            time.sleep(1)
            continue
        except WebSocketConnectionClosedException:
            raise Exception(
                f"Failed to exec commands with {retries} retries due to closed connection"
            )
    raise Exception(f"Failed to exec commands with {retries} retries")


def stream_exec(name: str, namespace: str, container: str, commands: List[str]):
    from kubernetes.stream import stream

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

    last_ouput = None
    while resp.is_open():
        resp.update(timeout=1)
        if resp.peek_stdout():
            last_ouput = resp.read_stdout()
        if resp.peek_stderr():
            last_ouput = resp.read_stderr()
            logger.error(f"Error from carrier2: {last_ouput}")
            break
        if commands:
            c = commands.pop(0)
            resp.write_stdin(c + "\n")
        else:
            break

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


# https://github.com/kubernetes-client/python/issues/476
def send_carrier2_config(name: str, namespace: str, content):
    # Calling exec interactively.
    commands = [
        "cat <<'EOF' >" + "/tmp/config.yaml" + "\n",
        content,
        "\n",
    ]
    stream_exec_retries(name, namespace, commands)


def reload_carrier2_config(name: str, namespace: str):
    commands = [
        "kill -SIGQUIT $(ps | grep '[c]arrier2' | awk ' { print $1 }' | tail -1) && carrier2 -c /tmp/config.yaml -u &"
    ]
    stream_exec_retries(name, namespace, commands)
