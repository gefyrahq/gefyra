from typing import List


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