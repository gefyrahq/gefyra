import os
import re
import uuid
from pathlib import Path
from subprocess import SubprocessError

import pytest

from tests.conftest import purge_gefyra_objects


def _collect_failure_diagnostics(item, report):
    cluster = item.funcargs.get("operator") or item.funcargs.get("k3d")
    if cluster is None:
        return

    commands = [
        ["get", "pods", "-A", "-o", "wide"],
        ["get", "deployments,replicasets,statefulsets", "-n", "default", "-o", "wide"],
        [
            "get",
            "gefyrabridges.gefyra.dev,gefyrabridgemounts.gefyra.dev",
            "-n",
            "gefyra",
            "-o",
            "yaml",
        ],
        ["get", "events", "-A", "--sort-by=.metadata.creationTimestamp"],
        ["describe", "pods", "-n", "gefyra"],
        [
            "logs",
            "-n",
            "gefyra",
            "deployment/gefyra-operator",
            "--all-containers=true",
            "--timestamps=true",
            "--tail=1000",
            "--pod-running-timeout=10s",
        ],
        [
            "logs",
            "-n",
            "gefyra",
            "gefyra-stowaway-0",
            "--all-containers=true",
            "--timestamps=true",
            "--tail=200",
            "--pod-running-timeout=10s",
        ],
    ]
    sections = [f"Test: {item.nodeid} ({report.when})"]
    for command in commands:
        sections.append("$ kubectl " + " ".join(command))
        try:
            sections.append(cluster.kubectl(command, as_dict=False, timeout=15))
        except (OSError, RuntimeError, SubprocessError) as error:
            # One unavailable resource must not prevent the remaining diagnostics.
            sections.append(f"{type(error).__name__}: {error}")
    diagnostics = "\n\n".join(sections)
    report.sections.append(("Gefyra cluster diagnostics", diagnostics))

    output_dir = os.environ.get("GEFYRA_TEST_DIAGNOSTICS_DIR")
    if output_dir:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^a-zA-Z0-9_.-]", "_", item.nodeid)
        path = directory / f"{name}-{report.when}-{uuid.uuid4().hex[:8]}.log"
        path.write_text(diagnostics, encoding="utf-8")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.failed:
        try:
            # Capture call failures before fixture teardown deletes the cluster.
            _collect_failure_diagnostics(item, report)
        except Exception as error:  # noqa: BLE001 - Preserve the original test failure.
            report.sections.append(("Gefyra diagnostics error", str(error)))


@pytest.fixture(scope="class", autouse=True)
def clear_gefyra_clients(operator):
    yield
    purge_gefyra_objects(operator)
