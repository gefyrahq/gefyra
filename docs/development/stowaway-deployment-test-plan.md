# Issue #1441: deployment and test plan

Status: implementation and local checks only. No deployment, image push, or cluster integration tests have been performed. Execute this plan only after the user authorizes deployment and testing against a named target.

## Deliverables and build prerequisites

Branch: `feat/#1441`, based on `main` at `7f95d2c2`.

The client is packaged as a Python wheel and source archive, with a usable CLI entry point. A standalone PyApp executable has not been built. Its package version remains 2.5.6; identify this development build by the branch/source revision and artifact checksum, not the release version alone. Install the development wheel into a separate environment so the normal client remains available for rollback.

The production image set is operator, stowaway, cargo, cargo-win, and carrier2. Operator-webhook uses the operator image. Local build attempts use the tag `localhost/gefyra/<component>:feat-1441-dev` and target Linux amd64; cross-architecture publication is a separate release step. The carrier2 Dockerfile currently targets amd64.

Before deployment, complete all image builds using a builder with access to upstream base-image registries and build-time dependency sources. Do not substitute unrelated base images to work around a pull failure. Record successful image IDs/digests, source revision, build logs, and the client checksum. Publish to an agreed development registry only after authorization. No production tags should be overwritten.

The source change affects the client and operator image. The remaining images are rebuilt for a consistent development bundle, although their source is unchanged.

## 1. Select the test environment

Use a disposable, isolated Kubernetes cluster with at least two worker nodes. Do not use shared Gefyra infrastructure for the first deployment. Agree the exact kubeconfig/context, namespace, development registry, and storage class before execution.

Choose two nodes or pools with distinct labels. Provide one tainted pool/node for the toleration case. Verify that the target nodes support stowaway's privileged container, WireGuard, required networking, and storage topology. Use a disposable PVC for tests involving cross-node relocation; preserve any pre-existing data.

If later validation needs shared infrastructure, coordinate an explicit maintenance window and deployment ownership first. Active connections will be interrupted when stowaway's pod template changes.

## 2. Prepare reviewable installation manifests

Use the wheel-installed development client to generate manifests without `--apply`. Select the development image registry/tag explicitly. Inspect every image reference, including the operator-webhook image, before applying anything.

Keep two reviewed manifests: baseline defaults and configured stowaway. The configured manifest should include a node-pool selector, a matching toleration, a supplemental pod label, and a startup failure threshold of 60. Keep operator/webhook scheduling in their own Deployment overlays if needed.

For an existing installation, snapshot the operator/webhook Deployments and stowaway StatefulSet metadata/spec plus PVC identity. Exclude secrets and connection key material from saved evidence. Apply Deployment updates through the chosen manifest-management process; do not assume `gefyra install --apply` upgrades existing Deployments.

## 3. Validate a fresh installation

After authorization, install with the configured manifest. Verify:

- The operator and webhook are healthy, and stowaway becomes ready.
- The stowaway StatefulSet template contains the exact selector, tolerations, merged pod labels, and startup threshold.
- The actual stowaway pod is scheduled onto a matching node.
- The StatefulSet and Service selectors contain only the original built-in selector labels.
- The configured toleration permits placement on the intended tainted node.
- The pod remains Pending when no node matches the selector; collect scheduling events, then restore a valid configuration.

Do not infer successful placement from the desired template alone; record the actual pod node and matching node labels.

## 4. Validate updates, resets, and reconciliation

On an existing ready installation, change configuration and restart/update the operator via its Deployment. Exercise both same-image configuration changes and a development operator upgrade.

- Add and change selector entries; verify the resulting pod placement.
- Add multiple tolerations, including repeated keys with different effects, and a `NoExecute` toleration with `tolerationSeconds`.
- Add/change/remove supplemental labels. Add a separate external label to the pod template and confirm it survives resets.
- Reject conflicting built-in label values before deployment.
- Reset selectors and labels to `{}`, tolerations to `[]`, and the startup threshold to 3.
- Confirm the StatefulSet UID, selectors, and PVC identity remain unchanged through updates.
- Restart the operator without changing configuration. Confirm no unnecessary StatefulSet patch, new ControllerRevision, or pod replacement occurs.

Capture StatefulSet generation, ControllerRevision, pod UID, PVC UID, desired fields, and actual node placement before/after each meaningful change. A configuration reset restores policy; it does not guarantee relocation to the node used before testing.

## 5. Validate slow startup and client behavior

In the isolated test environment, delay stowaway's probe response in a controlled, reversible way. Compare the default threshold of 3 with 60 using a delay that exceeds the default budget but fits the configured budget. Confirm successful startup without premature restarts and normal readiness/liveness behavior afterward. Keep the operator's separate startup-wait limit large enough.

Create a development connection with the new client, verify WireGuard health, and bridge a disposable workload. Confirm matching traffic reaches the local test service and non-matching traffic follows the cluster workload. Change stowaway configuration, observe the expected interruption, and confirm connection/bridge recovery.

## 6. Rollback and completion

Restore the captured Deployment manifests and stowaway settings, verify expected placement and health, and confirm client connectivity. If reverting to an older operator, explicitly restore the desired stowaway template as well; older operators may not reconcile the new fields. Do not delete or recreate the StatefulSet/PVC as a rollback shortcut.

After reviewing the evidence, remove only disposable test resources. Record remaining limitations, successful image digests, tested Kubernetes version/platform, and the final go/no-go decision before any shared-environment rollout.

## Local validation completed

- Client unit tests: 195 passed. The existing version-command test was run with its GitHub release lookup mocked in the local test harness; its repository source is unchanged.
- Operator unit tests: 79 passed, including configuration parsing, template generation, explicit resets, preservation of PVCs/selectors/external metadata, creation conflicts, concurrent-update retries, no-op reconciliation, and waiting for the reconciled pod revision before reporting readiness.
- Ruff checks/formatting and targeted mypy checks passed.
- Client wheel and source distribution built; the installed wheel generated operator/webhook YAML containing all four new settings.
- Container builds remain blocked by external registry access in this environment. Build logs and packaged client artifacts are retained under the ignored `dist/issue-1441/` directory.
- Kubernetes scheduling, probe timing, PVC relocation, and connection/bridge recovery remain to be validated using the authorized environment selected in this plan.
