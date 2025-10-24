# https://github.com/kubernetes-client/python/issues/476
def send_carrier2_config(core_api, name: str, namespace: str, config_content: str):
    # Calling exec interactively.
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
    commands.append("cat <<'EOF' >" + "/tmp/config.yaml" + "\n")
    commands.append(config_content)
    commands.append("\n")

    while resp.is_open():
        resp.update(timeout=1)
        if resp.peek_stdout():
            print("STDOUT: %s" % resp.read_stdout())
        if resp.peek_stderr():
            print("STDERR: %s" % resp.read_stderr())

        if commands:
            c = commands.pop(0)
            resp.write_stdin(c)
        else:
            break

    resp.close()


def reload_carrier2_config(core_api, name: str, namespace: str):
    from kubernetes.stream import stream

    commands = [
        "RUST_LOG=debug; kill -SIGQUIT $(cat /tmp/carrier2.pid); if [ $? -eq 0 ]; then RUST_LOG=debug carrier2 -c /tmp/config.yaml -u -d; else RUST_LOG=debug carrier2 -c /tmp/config.yaml -d; fi"
    ]
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
    # commit the last command
    resp.write_stdin("\n")
    sdate = resp.readline_stdout(timeout=3)
