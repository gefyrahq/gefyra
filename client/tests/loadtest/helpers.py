"""
Loadtest helpers: structured logging, timing, metrics collection.
"""

import json
import logging
from pathlib import Path
import shutil
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from typing import List, Optional


logger = logging.getLogger("gefyra.loadtest")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    phase: str
    step: int
    action: str
    success: bool
    duration_s: float
    error: Optional[str] = None
    detail: Optional[str] = None


@dataclass
class PhaseResult:
    phase: str
    total_steps: int
    passed: int
    failed: int
    duration_s: float
    steps: List[StepResult] = field(default_factory=list)


class MetricsCollector:
    """Accumulates StepResult / PhaseResult objects for the whole run."""

    def __init__(self):
        self.phases: List[PhaseResult] = []
        self._current_phase: Optional[str] = None
        self._phase_steps: List[StepResult] = []
        self._phase_start: float = 0.0

    def begin_phase(self, name: str):
        self._current_phase = name
        self._phase_steps = []
        self._phase_start = time.perf_counter()
        logger.info(f"{'='*60}")
        logger.info(f"PHASE START: {name}")
        logger.info(f"{'='*60}")

    def record_step(self, result: StepResult):
        self._phase_steps.append(result)
        status = "OK" if result.success else "FAIL"
        msg = f"  [{status}] {result.action} (step {result.step}) — {result.duration_s:.2f}s"
        if result.error:
            msg += f" — {result.error}"
        if result.success:
            logger.info(msg)
        else:
            logger.error(msg)

    def end_phase(self):
        duration = time.perf_counter() - self._phase_start
        passed = sum(1 for s in self._phase_steps if s.success)
        failed = sum(1 for s in self._phase_steps if not s.success)
        pr = PhaseResult(
            phase=self._current_phase or "unknown",
            total_steps=len(self._phase_steps),
            passed=passed,
            failed=failed,
            duration_s=duration,
            steps=list(self._phase_steps),
        )
        self.phases.append(pr)
        logger.info(f"PHASE END: {pr.phase} — {pr.passed}/{pr.total_steps} passed in {pr.duration_s:.1f}s")
        return pr

    def summary(self) -> str:
        w = 70
        lines = ["\n" + "=" * w, "LOADTEST SUMMARY", "=" * w]
        total_pass = 0
        total_fail = 0
        total_duration = 0.0

        for pr in self.phases:
            total_pass += pr.passed
            total_fail += pr.failed
            total_duration += pr.duration_s

            durations = [s.duration_s for s in pr.steps if s.success]
            lines.append("")
            lines.append(f"  {pr.phase}")
            lines.append(
                f"    steps: {pr.passed}/{pr.total_steps} passed, "
                f"{pr.failed} failed"
            )
            lines.append(f"    wall:  {pr.duration_s:.1f}s")

            if durations:
                durations_sorted = sorted(durations)
                avg = sum(durations) / len(durations)
                p95_idx = max(0, int(len(durations_sorted) * 0.95) - 1)
                lines.append(
                    f"    step timing:  "
                    f"min={durations_sorted[0]:.2f}s  "
                    f"avg={avg:.2f}s  "
                    f"p95={durations_sorted[p95_idx]:.2f}s  "
                    f"max={durations_sorted[-1]:.2f}s"
                )

            # show the 3 slowest steps
            slowest = sorted(pr.steps, key=lambda s: s.duration_s, reverse=True)[:3]
            if slowest:
                lines.append("    slowest steps:")
                for s in slowest:
                    tag = "OK" if s.success else "FAIL"
                    lines.append(
                        f"      [{tag}] {s.duration_s:>6.2f}s  {s.action}"
                    )

            # show failed steps
            failed = [s for s in pr.steps if not s.success]
            if failed:
                lines.append("    failures:")
                for s in failed:
                    lines.append(
                        f"      {s.action}: {s.error}"
                    )

        lines.append("")
        lines.append("-" * w)
        result = "PASS" if total_fail == 0 else "FAIL"
        lines.append(
            f"  RESULT: {result}  |  "
            f"{total_pass} passed, {total_fail} failed  |  "
            f"total {total_duration:.1f}s"
        )
        lines.append("=" * w)
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(
            [asdict(p) for p in self.phases],
            indent=2,
        )


# ---------------------------------------------------------------------------
# Timing context manager
# ---------------------------------------------------------------------------

@contextmanager
def timed_step(metrics: MetricsCollector, phase: str, step: int, action: str):
    """Context manager that records a StepResult into the MetricsCollector."""
    start = time.perf_counter()
    result = StepResult(phase=phase, step=step, action=action, success=False, duration_s=0.0)
    try:
        yield result
        # Only mark success if the step didn't explicitly set success=False
        if result.success is False and result.error is None:
            result.success = True
    except Exception as e:
        result.success = False
        result.error = str(e)
        raise
    finally:
        result.duration_s = time.perf_counter() - start
        metrics.record_step(result)


# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

REQUIRED_BINARIES = ["docker", "k3d", "kubectl"]


def check_prerequisites():
    """Fail fast if required system binaries are missing."""
    missing = []
    for binary in REQUIRED_BINARIES:
        if shutil.which(binary) is None:
            missing.append(binary)
    if missing:
        raise EnvironmentError(
            f"Missing required binaries: {', '.join(missing)}. "
            "Please install them before running the loadtest."
        )


# ---------------------------------------------------------------------------
# k3d cluster helpers
# ---------------------------------------------------------------------------

def _run(cmd: list, **kwargs):
    """Run a subprocess, logging stderr on failure."""
    logger.debug(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        logger.error(f"Command failed (exit {result.returncode}): {' '.join(cmd)}")
        if result.stdout:
            logger.error(f"stdout: {result.stdout}")
        if result.stderr:
            logger.error(f"stderr: {result.stderr}")
        result.check_returncode()
    return result


CONTAINERD_TMPL = Path(__file__).resolve().parent / "k3d-containerd-config.toml.tmpl"


def create_k3d_cluster(name: str, agents: int = 1, agent_memory: str = "4G", server_memory: str = "4G"):
    logger.info(f"Creating k3d cluster '{name}' with {agents} agents ...")

    cmd = [
        "k3d", "cluster", "create", name,
        f"--agents={agents}",
        f"--agents-memory={agent_memory}",
        f"--servers-memory={server_memory}",
        '--port=31820:31820/UDP@agent:0',
        "-p", "8080:80@agent:0",
    ]

    # On systems with AppArmor, containerd inside k3d applies a default
    # AppArmor profile to pods — even privileged ones. This blocks coreutils
    # (readlink) which stowaway's wg-quick needs. We mount a custom containerd
    # config template that sets disable_apparmor = true.
    if _apparmor_active():
        logger.info("  AppArmor detected — mounting containerd config with disable_apparmor=true")
        tmpl_mount = f"{CONTAINERD_TMPL}:/var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl"
        cmd.extend([
            "--volume", f"{tmpl_mount}@server:*",
            "--volume", f"{tmpl_mount}@agent:*",
        ])

    _run(cmd)
    logger.info(f"k3d cluster '{name}' created.")


def _apparmor_active() -> bool:
    """Check if Docker is using AppArmor."""
    result = subprocess.run(
        ["docker", "info", "--format", "{{.SecurityOptions}}"],
        capture_output=True, text=True,
    )
    return "apparmor" in result.stdout.lower()


def delete_k3d_cluster(name: str):
    logger.info(f"Deleting k3d cluster '{name}' ...")
    _run(["k3d", "cluster", "delete", name])
    logger.info(f"k3d cluster '{name}' deleted.")


def get_kubeconfig(cluster_name: str) -> str:
    """Return the path to the kubeconfig for a k3d cluster."""
    result = _run(["k3d", "kubeconfig", "write", cluster_name])
    return result.stdout.strip()


def load_image_into_k3d(cluster_name: str, image: str):
    """Load a local Docker image into the k3d cluster."""
    _run(["k3d", "image", "import", image, "-c", cluster_name])


# ---------------------------------------------------------------------------
# Image build helpers
# ---------------------------------------------------------------------------

def build_image(name: str, dockerfile: str, context: str, build_args: dict | None = None):
    logger.info(f"Building image '{name}' ...")
    cmd = [
        "docker", "build",
        "-t", name,
        "--platform", "linux/amd64",
        "-f", dockerfile,
    ]
    for key, value in (build_args or {}).items():
        cmd.extend(["--build-arg", f"{key}={value}"])
    cmd.append(context)
    _run(cmd)
    logger.info(f"Image '{name}' built.")


# ---------------------------------------------------------------------------
# kubectl helpers
# ---------------------------------------------------------------------------

def kubectl_apply(filepath: str, kubeconfig: str):
    _run(["kubectl", "apply", "-f", filepath, "--kubeconfig", kubeconfig])


def kubectl_wait(
    resource: str,
    condition: str,
    namespace: str,
    kubeconfig: str,
    timeout: str = "120s",
):
    _run([
        "kubectl", "wait", resource,
        f"--for={condition}",
        "-n", namespace,
        f"--timeout={timeout}",
        "--kubeconfig", kubeconfig,
    ])


def kubectl_get_json(resource: str, namespace: str, kubeconfig: str) -> dict:
    result = _run([
        "kubectl", "get", resource,
        "-n", namespace,
        "-o", "json",
        "--kubeconfig", kubeconfig,
    ])
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)-5s] %(name)s — %(message)s"
    logging.basicConfig(level=level, format=fmt)
    # silence noisy libs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("kubernetes").setLevel(logging.WARNING)
    logging.getLogger("docker").setLevel(logging.WARNING)
