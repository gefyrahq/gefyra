#!/usr/bin/env python3
"""
Gefyra Loadtest — main orchestrator.

Usage:
    python -m tests.loadtest.loadtest [OPTIONS]

Run from the `client/` directory.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml

from tests.loadtest.helpers import (
    MetricsCollector,
    build_image,
    check_prerequisites,
    create_k3d_cluster,
    delete_k3d_cluster,
    get_kubeconfig,
    kubectl_apply,
    kubectl_wait,
    load_image_into_k3d,
    setup_logging,
)
from tests.loadtest.phases import (
    phase_connect_clients,
    phase_disconnect_clients,
    phase_create_mounts,
    phase_create_bridges,
    phase_remove_bridges,
)

logger = logging.getLogger("gefyra.loadtest")

# Path constants relative to the repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OPERATOR_DIR = REPO_ROOT / "operator"
STOWAWAY_DIR = REPO_ROOT / "stowaway"
CARGO_DIR = REPO_ROOT / "cargo"
CARRIER2_DIR = REPO_ROOT / "carrier2"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
WORKLOADS_DIR = Path(__file__).resolve().parent / "workloads"
PATCHES_DIR = Path(__file__).resolve().parent / "patches"


# ---------------------------------------------------------------------------
# Gefyra cluster-side setup
# ---------------------------------------------------------------------------

def setup_gefyra_with_install_api(
    kubeconfig: str,
    version: str = "",
    registry: str = "",
):
    """Use gefyra install API to deploy from published images.

    Args:
        version: Gefyra version tag (e.g. "2.1.0"). Empty = current client version.
        registry: Image registry (e.g. "quay.io/gefyra"). Empty = default.
    """
    os.environ["KUBECONFIG"] = kubeconfig
    from gefyra.api.install import install

    kwargs = {}
    if version:
        kwargs["version"] = version
    if registry:
        kwargs["registry"] = registry

    version_info = version or "current"
    registry_info = registry or "default"
    logger.info(
        f"Installing Gefyra via install API (version={version_info}, registry={registry_info}) ..."
    )
    install(apply=True, wait=True, kubeconfig=Path(kubeconfig), **kwargs)
    logger.info("Gefyra installed and ready.")


def setup_gefyra_with_local_builds(kubeconfig: str, cluster_name: str):
    """Build operator/stowaway/carrier2 locally, load into k3d, apply fixture.

    Uses the same image tags as tests/fixtures/operator.yaml expects:
      - operator:pytest  (container image for the operator deployment)
      - stowaway:pytest  (referenced via GEFYRA_STOWAWAY_IMAGE/TAG env vars)
      - carrier2:pytest  (set via GEFYRA_CARRIER2_IMAGE/TAG env patch)
      - cargo:pytest     (used locally by connect(), not loaded into k3d)
    """
    logger.info("  [a] Building operator image (operator:pytest) ...")
    build_image(
        "operator:pytest",
        str(OPERATOR_DIR / "Dockerfile"),
        str(OPERATOR_DIR),
        build_args={"COMMIT_SHA": "loadtest"},
    )
    logger.info("  [b] Building stowaway image (stowaway:pytest) ...")
    build_image(
        "stowaway:pytest-base",
        str(STOWAWAY_DIR / "Dockerfile"),
        str(STOWAWAY_DIR),
    )
    # Apply kernel 6.x overlayfs wg-quick workaround on top
    build_image(
        "stowaway:pytest",
        str(PATCHES_DIR / "Dockerfile.stowaway"),
        str(PATCHES_DIR),
        build_args={"BASE_IMAGE": "stowaway:pytest-base"},
    )
    logger.info("  [c] Building cargo image (cargo:pytest) ...")
    build_image(
        "cargo:pytest-base",
        str(CARGO_DIR / "Dockerfile"),
        str(CARGO_DIR),
    )
    # Apply kernel 6.x overlayfs wg-quick workaround on top
    build_image(
        "cargo:pytest",
        str(PATCHES_DIR / "Dockerfile.cargo"),
        str(PATCHES_DIR),
        build_args={"BASE_IMAGE": "cargo:pytest-base"},
    )
    logger.info("  [d] Building carrier2 image (carrier2:pytest) ...")
    build_image(
        "carrier2:pytest",
        str(CARRIER2_DIR / "Dockerfile"),
        str(CARRIER2_DIR),
    )

    logger.info("  [e] Loading images into k3d cluster ...")
    for img in ("operator:pytest", "stowaway:pytest", "carrier2:pytest"):
        logger.info(f"       Importing {img} ...")
        load_image_into_k3d(cluster_name, img)

    logger.info("  [f] Creating gefyra namespace ...")
    subprocess.run(
        ["kubectl", "create", "ns", "gefyra", "--kubeconfig", kubeconfig],
        check=False,  # may already exist
    )

    # Apply operator fixture with carrier2 env vars included from the start
    # (avoids a restart from kubectl set env, which causes kopf handler races)
    operator_yaml = FIXTURES_DIR / "operator.yaml"
    logger.info(f"  [g] Applying operator manifest (with carrier2:pytest) ...")
    _apply_operator_with_carrier2(operator_yaml, kubeconfig)

    logger.info("  [h] Waiting for Gefyra to become ready (operator + stowaway) ...")
    _wait_for_gefyra_ready(kubeconfig)
    logger.info("  Gefyra (local build) installed and ready.")


def _apply_operator_with_carrier2(operator_yaml: Path, kubeconfig: str):
    """Load the operator fixture YAML, inject carrier2 env vars, and apply."""
    with open(operator_yaml) as f:
        docs = list(yaml.safe_load_all(f))

    for doc in docs:
        if doc and doc.get("kind") == "Deployment":
            containers = doc["spec"]["template"]["spec"]["containers"]
            for c in containers:
                if c["name"] == "gefyra-operator":
                    env = c.setdefault("env", [])
                    env.append({"name": "GEFYRA_CARRIER2_IMAGE", "value": "carrier2"})
                    env.append({"name": "GEFYRA_CARRIER2_IMAGE_TAG", "value": "pytest"})

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as tmp:
        yaml.dump_all(docs, tmp, default_flow_style=False)
        tmp_path = tmp.name

    kubectl_apply(tmp_path, kubeconfig)
    os.unlink(tmp_path)


def _wait_for_gefyra_ready(kubeconfig: str, timeout: int = 180):
    """Poll K8s events for the Gefyra-Ready event."""
    start = datetime.now(timezone.utc)
    for i in range(timeout):
        time.sleep(1)
        result = subprocess.run(
            [
                "kubectl", "get", "events",
                "-n", "gefyra",
                "-o", "json",
                "--kubeconfig", kubeconfig,
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            continue
        events = json.loads(result.stdout)
        for event in events.get("items", []):
            event_time = event.get("eventTime") or event.get("lastTimestamp")
            if not event_time:
                continue
            if event.get("reason") == "Gefyra-Ready":
                et = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                if et > start:
                    logger.info(f"       Gefyra-Ready event received after {i+1}s")
                    return

        # Every 15s, log pod status so the user can see progress
        if (i + 1) % 15 == 0:
            logger.info(f"       ... still waiting ({i+1}/{timeout}s)")
            _log_gefyra_pod_status(kubeconfig)

    # Final diagnostic dump before raising
    _log_gefyra_pod_status(kubeconfig)
    _log_gefyra_pod_logs(kubeconfig)
    raise TimeoutError(f"Gefyra-Ready event not found within {timeout}s")


def _log_gefyra_pod_status(kubeconfig: str):
    """Log current pod status in the gefyra namespace."""
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", "gefyra", "-o", "wide", "--kubeconfig", kubeconfig],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        logger.warning(f"Gefyra pod status:\n{result.stdout}")


def _log_gefyra_pod_logs(kubeconfig: str):
    """Dump recent logs from crashing/failing pods in the gefyra namespace."""
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", "gefyra", "-o", "json", "--kubeconfig", kubeconfig],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return
    pods = json.loads(result.stdout)
    for pod in pods.get("items", []):
        name = pod["metadata"]["name"]
        phase = pod.get("status", {}).get("phase", "")
        statuses = pod.get("status", {}).get("containerStatuses", [])
        is_unhealthy = phase != "Running" or any(
            not cs.get("ready", False) for cs in statuses
        )
        if is_unhealthy:
            log_result = subprocess.run(
                ["kubectl", "logs", "-n", "gefyra", name, "--tail=30", "--kubeconfig", kubeconfig],
                capture_output=True, text=True,
            )
            if log_result.returncode == 0 and log_result.stdout.strip():
                logger.error(f"Logs for unhealthy pod {name}:\n{log_result.stdout}")
            # Also try previous container logs for CrashLoopBackOff
            log_result = subprocess.run(
                ["kubectl", "logs", "-n", "gefyra", name, "--previous", "--tail=30", "--kubeconfig", kubeconfig],
                capture_output=True, text=True,
            )
            if log_result.returncode == 0 and log_result.stdout.strip():
                logger.error(f"Previous logs for {name}:\n{log_result.stdout}")


# ---------------------------------------------------------------------------
# Target workload deployment
# ---------------------------------------------------------------------------

def deploy_workloads(kubeconfig: str, workload: str):
    """Apply the chosen workload manifest into the cluster."""
    manifest = WORKLOADS_DIR / f"{workload}.yaml"
    if not manifest.exists():
        raise FileNotFoundError(f"Workload manifest not found: {manifest}")
    logger.info(f"Deploying workload '{workload}' from {manifest}")

    kubectl_apply(str(manifest), kubeconfig)

    # Wait for the deployment to become ready
    deployment_name = f"hello-nginxdemo-{workload}"
    kubectl_wait(
        resource=f"deployment/{deployment_name}",
        condition="condition=available",
        namespace="default",
        kubeconfig=kubeconfig,
        timeout="120s",
    )
    logger.info(f"Workload '{workload}' is ready.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("--num-clients", default=200, show_default=True, help="Number of clients to connect in Phase 1.")
@click.option("--num-mounts", default=20, show_default=True, help="Number of mounts to create.")
@click.option("--bridges-per-mount", default=20, show_default=True, help="Bridges per mount.")
@click.option("--workload", default="light", type=click.Choice(["light", "medium", "heavy"]), show_default=True, help="Target workload profile.")
@click.option("--workload-target", default=None, help="Workload target string (e.g. 'deployment/hello-nginxdemo-light/hello-nginx'). Auto-derived from --workload if omitted.")
@click.option("--workload-namespace", default="default", show_default=True, help="Namespace for the target workload.")
@click.option("--local-image", default="quay.io/gefyra/pyserver:latest", show_default=True, help="Local container image for bridge targets.")
@click.option("--cluster-name", default="gefyra-loadtest", show_default=True, help="k3d cluster name.")
@click.option("--setup-cluster/--no-setup-cluster", default=True, show_default=True, help="Create the k3d cluster.")
@click.option("--teardown-cluster/--no-teardown-cluster", default=True, show_default=True, help="Delete the k3d cluster on exit.")
@click.option("--build-images/--no-build-images", default=False, show_default=True, help="Build operator/stowaway locally instead of using published images.")
@click.option("--gefyra-version", default="", help="Gefyra version to install (e.g. '2.1.0'). Only used without --build-images. Empty = current client version.")
@click.option("--gefyra-registry", default="", help="Image registry (e.g. 'quay.io/gefyra'). Only used without --build-images. Empty = default.")
@click.option("--delay", default=1.0, show_default=True, help="Delay (seconds) between steps.")
@click.option("--output-json", default=None, type=click.Path(), help="Write JSON metrics to this file.")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.option(
    "--phases",
    default="connect_clients,create_mounts,create_bridges,remove_bridges,disconnect_clients",
    show_default=True,
    help="Comma-separated list of phases to run (e.g. 'connect_clients,disconnect_clients').",
)
def main(
    num_clients,
    num_mounts,
    bridges_per_mount,
    workload,
    workload_target,
    workload_namespace,
    local_image,
    cluster_name,
    setup_cluster,
    teardown_cluster,
    build_images,
    gefyra_version,
    gefyra_registry,
    delay,
    output_json,
    verbose,
    phases,
):
    """Gefyra Loadtest — stress the operator with many clients, mounts, and bridges."""
    setup_logging(verbose)
    check_prerequisites()

    phases_to_run = {p.strip() for p in phases.split(",")}

    # Derive workload target if not explicitly given
    if not workload_target:
        workload_target = f"deployment/hello-nginxdemo-{workload}/hello-nginx"

    metrics = MetricsCollector()
    kubeconfig = None

    total_setup_steps = 4 + (1 if setup_cluster else 0)

    try:
        step = 0
        logger.info("=" * 60)
        logger.info("SETUP")
        logger.info("=" * 60)

        # --- Cluster setup ---
        if setup_cluster:
            step += 1
            logger.info(f"[Setup {step}/{total_setup_steps}] Creating k3d cluster '{cluster_name}' ...")
            create_k3d_cluster(cluster_name)

        step += 1
        logger.info(f"[Setup {step}/{total_setup_steps}] Fetching kubeconfig ...")
        kubeconfig = get_kubeconfig(cluster_name)
        os.environ["KUBECONFIG"] = kubeconfig
        logger.info(f"  KUBECONFIG={kubeconfig}")

        # --- Gefyra install ---
        step += 1
        if build_images:
            logger.info(f"[Setup {step}/{total_setup_steps}] Installing Gefyra (local build) ...")
            setup_gefyra_with_local_builds(kubeconfig, cluster_name)
        else:
            version_info = gefyra_version or "current"
            logger.info(f"[Setup {step}/{total_setup_steps}] Installing Gefyra (version={version_info}) ...")
            setup_gefyra_with_install_api(
                kubeconfig,
                version=gefyra_version,
                registry=gefyra_registry,
            )

        # --- Clean up stale loadtest resources from previous runs ---
        logger.info("  Cleaning up stale loadtest resources ...")
        for resource in ("gefyraclients", "gefyrabridgemounts", "gefyrabridges"):
            subprocess.run(
                ["kubectl", "delete", resource, "--all",
                 "-n", "gefyra", "--kubeconfig", kubeconfig],
                capture_output=True, check=False,
            )

        # --- Deploy target workload ---
        step += 1
        logger.info(f"[Setup {step}/{total_setup_steps}] Deploying target workload '{workload}' ...")
        deploy_workloads(kubeconfig, workload)

        # --- Pull local image ---
        step += 1
        logger.info(f"[Setup {step}/{total_setup_steps}] Pulling local container image '{local_image}' ...")
        subprocess.run(["docker", "pull", local_image], check=True)

        logger.info("=" * 60)
        logger.info("SETUP COMPLETE — starting loadtest phases")
        logger.info(f"  Clients: {num_clients}, Mounts: {num_mounts}, Bridges/mount: {bridges_per_mount}")
        logger.info(f"  Phases: {phases}")
        logger.info("=" * 60)

        # =================================================================
        # Connect clients
        # =================================================================
        cargo_image = "cargo:pytest" if build_images else ""
        connections = []
        if "connect_clients" in phases_to_run:
            connections = phase_connect_clients.run_phase(
                metrics=metrics,
                num_clients=num_clients,
                delay_between=delay,
                cargo_image=cargo_image,
                kubeconfig=kubeconfig,
            )

        # =================================================================
        # Create mounts
        # =================================================================
        mount_client_id = None
        mount_connection_name = None
        mount_names = []
        if "create_mounts" in phases_to_run:
            mount_client_id, mount_connection_name, mount_names = phase_create_mounts.run_phase(
                metrics=metrics,
                num_mounts=num_mounts,
                workload_target=workload_target,
                workload_namespace=workload_namespace,
                kubeconfig=kubeconfig,
                cargo_image=cargo_image,
            )

        # =================================================================
        # Create bridges
        # =================================================================
        bridge_records = []
        if "create_bridges" in phases_to_run and mount_names and mount_connection_name:
            bridge_records = phase_create_bridges.run_phase(
                metrics=metrics,
                connection_name=mount_connection_name,
                mount_names=mount_names,
                bridges_per_mount=bridges_per_mount,
                local_image=local_image,
                kubeconfig=kubeconfig,
                delay_between=delay,
            )

        # =================================================================
        # Remove bridges
        # =================================================================
        if "remove_bridges" in phases_to_run and bridge_records and mount_connection_name:
            phase_remove_bridges.run_phase(
                metrics=metrics,
                bridge_records=bridge_records,
                connection_name=mount_connection_name,
                delay_between=delay,
            )

        # =================================================================
        # Disconnect clients
        # =================================================================
        if "disconnect_clients" in phases_to_run and connections:
            phase_disconnect_clients.run_phase(
                metrics=metrics,
                connections=connections,
                delay_between=delay,
            )

    except Exception:
        logger.exception("Loadtest failed with an unhandled error")
        raise
    finally:
        # --- Summary ---
        print(metrics.summary())

        # --- JSON output ---
        if output_json:
            with open(output_json, "w") as fh:
                fh.write(metrics.to_json())
            logger.info(f"Metrics written to {output_json}")

        # --- Cluster teardown ---
        if teardown_cluster and setup_cluster:
            try:
                delete_k3d_cluster(cluster_name)
            except Exception:
                logger.exception("Failed to delete cluster")


if __name__ == "__main__":
    main()
