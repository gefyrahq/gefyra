from subprocess import TimeoutExpired
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.e2e.conftest import (
    _collect_failure_diagnostics,
    pytest_runtest_makereport,
)


def test_diagnostics_continue_after_a_command_timeout(monkeypatch, tmp_path):
    monkeypatch.setenv("GEFYRA_TEST_DIAGNOSTICS_DIR", str(tmp_path))

    def kubectl(command, **kwargs):
        assert kwargs == {"as_dict": False, "timeout": 15}
        if command[:2] == ["get", "pods"]:
            raise TimeoutExpired("kubectl", 15)
        if command[0] == "logs":
            return "operator recovery details"
        return "cluster state"

    cluster = SimpleNamespace(kubectl=Mock(side_effect=kubectl))
    item = SimpleNamespace(
        funcargs={"operator": cluster}, nodeid="test_bridge.py::test_recovery[no_sa]"
    )
    report = SimpleNamespace(when="call", sections=[])

    _collect_failure_diagnostics(item, report)
    _collect_failure_diagnostics(item, report)

    snapshots = list(tmp_path.glob("*.log"))
    assert len(snapshots) == 2  # A retry must not overwrite the first failure.
    for snapshot in snapshots:
        text = snapshot.read_text()
        assert "TimeoutExpired" in text
        assert "gefyrabridges.gefyra.dev,gefyrabridgemounts.gefyra.dev" in text
        assert "deployment/gefyra-operator" in text
        assert "operator recovery details" in text
    assert len(report.sections) == 2


def test_diagnostics_skip_failures_without_a_cluster(monkeypatch, tmp_path):
    monkeypatch.setenv("GEFYRA_TEST_DIAGNOSTICS_DIR", str(tmp_path))
    item = SimpleNamespace(funcargs={}, nodeid="test_setup")
    report = SimpleNamespace(when="setup", sections=[])

    _collect_failure_diagnostics(item, report)

    assert report.sections == []
    assert list(tmp_path.iterdir()) == []


def test_diagnostics_storage_error_does_not_mask_test_failure(monkeypatch, tmp_path):
    output = tmp_path / "not-a-directory"
    output.write_text("existing file")
    monkeypatch.setenv("GEFYRA_TEST_DIAGNOSTICS_DIR", str(output))
    cluster = SimpleNamespace(kubectl=Mock(return_value="cluster state"))
    item = SimpleNamespace(funcargs={"operator": cluster}, nodeid="test_recovery")
    report = SimpleNamespace(failed=True, when="call", sections=[])
    hook = pytest_runtest_makereport(item, None)
    next(hook)

    with pytest.raises(StopIteration):
        hook.send(SimpleNamespace(get_result=lambda: report))

    assert report.failed
    assert report.sections[0][0] == "Gefyra cluster diagnostics"
    assert report.sections[1][0] == "Gefyra diagnostics error"
