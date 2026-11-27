import os
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize(
    "peer_id, directory", [("client-a", "peer_client000a"), ("123", "peer123")]
)
@pytest.mark.parametrize(
    "state",
    [
        "absent",
        "directory",
        "server_config",
        "unknown_live",
        "wg_failure",
        "missing_config",
    ],
)
async def test_runtime_probe_checks_disk_and_live_state(
    monkeypatch, tmp_path, peer_id, directory, state
):
    import gefyra.connection.stowaway as module

    provider = module.Stowaway(SimpleNamespace(NAMESPACE="gefyra"), Mock())
    pod = SimpleNamespace(
        metadata=SimpleNamespace(name="stowaway-0", namespace="gefyra")
    )
    # Run the actual probe shell against an isolated filesystem and fake wg binary.
    config = tmp_path / "config"
    config.mkdir()
    if state != "missing_config":
        server_config = "[Interface]\n[Peer]\n# peer_other\nPublicKey = other-key\n"
        if state == "server_config":
            server_config += f"[Peer]\n# {directory}\nPublicKey = target-key\n"
        (config / "wg0.conf").write_text(server_config)
    if state == "directory":
        (config / directory).mkdir()
    wg = tmp_path / "wg"
    if state == "wg_failure":
        wg.write_text("#!/bin/sh\nexit 1\n")
    else:
        keys = "unknown-key" if state == "unknown_live" else "other-key"
        if state == "server_config":
            keys += " target-key"
        wg.write_text(f"#!/bin/sh\nprintf '%s\\n' '{keys}'\n")
    wg.chmod(0o755)

    def exec_command(api, name, namespace, container, command):
        assert command[-2] == directory
        command = [*command[:-1], str(config)]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env={**os.environ, "PATH": f"{tmp_path}:/usr/bin:/bin"},
        )
        return result.stdout + result.stderr

    monkeypatch.setattr(module, "exec_command_pod", exec_command)
    if state in ("unknown_live", "wg_failure", "missing_config"):
        with pytest.raises(RuntimeError, match="Cannot establish runtime peer state"):
            await provider._peer_runtime_exists(peer_id, pod)
    else:
        assert await provider._peer_runtime_exists(peer_id, pod) == (state != "absent")


async def test_runtime_probe_preserves_transport_errors(monkeypatch):
    import gefyra.connection.stowaway as module

    provider = module.Stowaway(SimpleNamespace(NAMESPACE="gefyra"), Mock())
    pod = SimpleNamespace(
        metadata=SimpleNamespace(name="stowaway-0", namespace="gefyra")
    )
    error = module.k8s.client.ApiException(status=0, reason="exec failed")
    monkeypatch.setattr(module, "exec_command_pod", Mock(side_effect=error))
    with pytest.raises(module.k8s.client.ApiException) as raised:
        await provider._peer_runtime_exists("client-a", pod)
    assert raised.value is error
