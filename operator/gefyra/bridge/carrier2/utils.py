from typing import List
import time


def stream_exec_retries(
    core_api, name: str, namespace: str, commands: List[str], retries: int = 5
):
    from kubernetes.client.rest import ApiException

    while retries > 0:
        try:
            stream_exec(core_api, name, namespace, commands)
            break
        except ApiException:
            retries -= 1
            time.sleep(1)
            continue


def stream_exec(core_api, name: str, namespace: str, commands: List[str]):
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
def send_carrier2_config(core_api, name: str, namespace: str, config_content: str):
    # Calling exec interactively.
    commands = ["cat <<'EOF' >" + "/tmp/config.yaml" + "\n", config_content, "\n"]
    stream_exec_retries(core_api, name, namespace, commands)


def reload_carrier2_config(core_api, name: str, namespace: str):
    commands = [
        "kill -SIGQUIT $(ps | grep '[c]arrier2' | awk ' { print $1 }' | tail -1) && carrier2 -c /tmp/config.yaml -u &"
    ]
    stream_exec_retries(core_api, name, namespace, commands)
