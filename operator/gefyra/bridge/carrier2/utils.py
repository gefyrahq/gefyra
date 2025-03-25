from typing import List
import time

import kubernetes as k8s

core_v1_api = k8s.client.CoreV1Api()


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
    raise Exception(f"Failed to exec commands with {retries} retries")


def stream_exec(name: str, namespace: str, commands: List[str]):
    from kubernetes.stream import stream

    exec_command = ["busybox", "sh"]
    resp = stream(
        core_v1_api.connect_get_namespaced_pod_exec,
        name,
        namespace,
        command=exec_command,
        stderr=True,
        stdin=True,
        stdout=True,
        tty=False,
        _preload_content=False,
    )

    while resp.is_open():
        resp.update(timeout=1)
        if resp.peek_stdout():
            print(f"STDOUT: {resp.read_stdout()}")
        if resp.peek_stderr():
            print(f"STDERR: {resp.read_stderr()}")

        if commands:
            c = commands.pop(0)
            resp.write_stdin(c)
        else:
            break
    resp.write_stdin("\n")
    resp.readline_stdout(timeout=3)
    resp.close()


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
