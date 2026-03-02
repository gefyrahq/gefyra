# Gefyra Loadtest (GO-1016)

Stress-test the Gefyra operator, WireGuard tunnels, mounts, and bridges at scale.

## Prerequisites

- **Docker** — running, with enough headroom for 200+ containers
- **k3d** — cluster lifecycle
- **kubectl**
- **Python dependencies** — install the loadtest group:
  ```bash
  cd client/
  poetry install --with loadtest
  ```

## Quick Start

```bash
# From client/ directory — full 200-client run with local builds
python -m tests.loadtest --build-images

# Small smoke test
python -m tests.loadtest --build-images --num-clients 3 --num-mounts 1 --bridges-per-mount 2

# Skip cluster create/destroy for fast iteration (kubeconfig is auto-fetched from k3d)
python -m tests.loadtest --build-images --no-setup-cluster --no-teardown-cluster

# Run specific phases only
python -m tests.loadtest --build-images --phases connect_clients,create_mounts

# Test a specific published Gefyra version (no local builds)
python -m tests.loadtest --gefyra-version 2.1.0

# Test from a custom registry
python -m tests.loadtest --gefyra-version 2.0.0 --gefyra-registry ghcr.io/gefyrahq
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--num-clients` | 200 | Clients to connect |
| `--num-mounts` | 20 | Mounts to create |
| `--bridges-per-mount` | 20 | Bridges per mount |
| `--workload` | light | Target workload: `light`, `medium`, `heavy` |
| `--workload-target` | auto | Override target string (e.g. `deployment/my-app/my-container`) |
| `--workload-namespace` | default | Namespace for target workload |
| `--local-image` | quay.io/gefyra/pyserver:latest | Local container image for bridges |
| `--cluster-name` | gefyra-loadtest | k3d cluster name |
| `--setup-cluster / --no-setup-cluster` | true | Create the k3d cluster |
| `--teardown-cluster / --no-teardown-cluster` | true | Delete cluster on exit |
| `--build-images / --no-build-images` | false | Build operator/stowaway/cargo/carrier2 locally from working tree |
| `--gefyra-version` | _(current)_ | Gefyra version to install (e.g. `2.1.0`). Only without `--build-images` |
| `--gefyra-registry` | _(default)_ | Image registry (e.g. `ghcr.io/gefyrahq`). Only without `--build-images` |
| `--delay` | 1.0 | Seconds between steps |
| `--output-json` | — | Write JSON metrics to file |
| `--phases` | _(all)_ | Phases to run (comma-separated, see below) |
| `-v` / `--verbose` | false | Debug logging |

## Phases

| Phase | What it does |
|-------|-------------|
| **connect_clients** | Gradually connect N clients; verify status UP after each |
| **create_mounts** | Quickly create N mounts (connects a dedicated client first) |
| **create_bridges** | Create bridges per mount with header-based routing; wait for ACTIVE; verify traffic routing for all bridges after each |
| **remove_bridges** | Gradually remove all bridges; verify remaining traffic routing still works after each removal |
| **disconnect_clients** | Gradually disconnect all clients connected in the first phase |

Phases are **additive**: each phase builds on the state left by previous phases.

Select specific phases with `--phases connect_clients,create_mounts`.

## Gefyra Integration

There are two ways to get Gefyra into the test cluster:

### Local builds (`--build-images`) — recommended for development

Builds `operator:pytest`, `stowaway:pytest`, `cargo:pytest`, and `carrier2:pytest`
from your working tree, loads them into k3d, and applies `tests/fixtures/operator.yaml`.
The stowaway and cargo images get an extra patch layer (`tests/loadtest/patches/`)
with a kernel 6.x overlayfs wg-quick workaround.

```bash
python -m tests.loadtest --build-images
```

### Published images (default)

Uses `gefyra.api.install.install(apply=True, wait=True)` — the same codepath as
`gefyra install --apply --wait`. By default this installs the version matching your
local client. Override with `--gefyra-version` and/or `--gefyra-registry` to test
against a different release:

```bash
# Current client version (whatever is in pyproject.toml)
python -m tests.loadtest

# Specific version
python -m tests.loadtest --gefyra-version 2.1.0
```

## Kernel 6.x Workaround

On systems with kernel 6.x+, overlayfs exec restrictions can cause `wg-quick`
to fail with `Permission denied` errors in stowaway and cargo containers. This
is not an AppArmor issue — it's a kernel restriction on shebang-based exec from
overlayfs.

The loadtest handles this with a two-stage Docker build:
1. Build the base image from the source Dockerfile
2. Layer a patch on top (`tests/loadtest/patches/`) that invokes wg-quick via
   explicit `bash /usr/bin/wg-quick` instead of the shebang path

Additionally, on systems where Docker reports AppArmor as active, the loadtest
auto-mounts a custom containerd config template (`k3d-containerd-config.toml.tmpl`)
into k3d nodes with `disable_apparmor = true`.

If you manage your own k3d cluster (`--no-setup-cluster`), you may need to apply
this workaround yourself:

```bash
k3d cluster create my-cluster \
  --volume "$PWD/tests/loadtest/k3d-containerd-config.toml.tmpl:/var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl@server:*" \
  --volume "$PWD/tests/loadtest/k3d-containerd-config.toml.tmpl:/var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl@agent:*"
```

## Traffic Verification

Phases create_bridges and remove_bridges verify traffic routing via HTTP:

- **Workload**: `nginxdemos/hello` behind an Ingress on `localhost:8080`
- **Local container**: `quay.io/gefyra/pyserver` responds with "Hello from Gefyra"
- Each bridge gets a unique header rule: `x-gefyra: peer-{mount}-{bridge}`
- After each bridge add/remove, all existing bridges are verified by sending
  HTTP requests with the appropriate headers and checking the response

Verification failures are recorded as failed steps in the metrics but do not
abort the loadtest — this lets you see how many bridges work vs. fail at scale.

## Output

- Structured log output with timing per step
- Summary at the end with per-phase statistics:
  - Pass/fail counts
  - Wall time
  - Step timing: min / avg / p95 / max
  - 3 slowest steps
  - Failed steps with error details
- Optional `--output-json metrics.json` for programmatic analysis / graphing

## Workload Profiles

| Profile | Replicas | CPU request/limit | Memory request/limit |
|---------|----------|--------------------|----------------------|
| light | 1 | 50m / 100m | 32Mi / 64Mi |
| medium | 2 | 100m / 250m | 64Mi / 128Mi |
| heavy | 3 | 200m / 500m | 128Mi / 256Mi |
