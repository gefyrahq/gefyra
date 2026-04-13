from copy import deepcopy
from unittest import TestCase


def _make_deployment():
    from kubernetes.client import (
        V1Container,
        V1ContainerPort,
        V1Deployment,
        V1DeploymentSpec,
        V1EnvVar,
        V1LabelSelector,
        V1ObjectMeta,
        V1PodSpec,
        V1PodTemplateSpec,
    )

    return V1Deployment(
        metadata=V1ObjectMeta(name="nginx", labels={"app": "nginx"}),
        spec=V1DeploymentSpec(
            replicas=1,
            selector=V1LabelSelector(match_labels={"app": "nginx"}),
            template=V1PodTemplateSpec(
                metadata=V1ObjectMeta(labels={"app": "nginx"}),
                spec=V1PodSpec(
                    containers=[
                        V1Container(
                            name="nginx",
                            image="nginx:1.27",
                            ports=[V1ContainerPort(container_port=80)],
                            env=[V1EnvVar(name="LOG_LEVEL", value="info")],
                        )
                    ]
                ),
            ),
        ),
    )


def _make_hpa(target_name="nginx", min_replicas=1, max_replicas=5):
    from kubernetes.client import (
        V1ObjectMeta,
        V2CrossVersionObjectReference,
        V2HorizontalPodAutoscaler,
        V2HorizontalPodAutoscalerSpec,
    )

    return V2HorizontalPodAutoscaler(
        metadata=V1ObjectMeta(name="hpa", namespace="default"),
        spec=V2HorizontalPodAutoscalerSpec(
            scale_target_ref=V2CrossVersionObjectReference(
                api_version="apps/v1", kind="Deployment", name=target_name
            ),
            min_replicas=min_replicas,
            max_replicas=max_replicas,
        ),
    )


class TestWorkloadHash(TestCase):
    def test_identical_deployments_hash_identically(self):
        from gefyra.bridge_mount.carrier2mount.source_hash import hash_workload_source

        a = _make_deployment()
        b = _make_deployment()
        self.assertEqual(hash_workload_source(a), hash_workload_source(b))

    def test_replica_change_does_not_change_hash(self):
        """HPA-driven replica changes on the source must not trigger shadow
        churn, so the hash ignores spec.replicas."""
        from gefyra.bridge_mount.carrier2mount.source_hash import hash_workload_source

        a = _make_deployment()
        b = deepcopy(a)
        b.spec.replicas = 42
        self.assertEqual(hash_workload_source(a), hash_workload_source(b))

    def test_image_change_changes_hash(self):
        from gefyra.bridge_mount.carrier2mount.source_hash import hash_workload_source

        a = _make_deployment()
        b = deepcopy(a)
        b.spec.template.spec.containers[0].image = "nginx:1.28"
        self.assertNotEqual(hash_workload_source(a), hash_workload_source(b))

    def test_env_change_changes_hash(self):
        from gefyra.bridge_mount.carrier2mount.source_hash import hash_workload_source

        a = _make_deployment()
        b = deepcopy(a)
        b.spec.template.spec.containers[0].env[0].value = "debug"
        self.assertNotEqual(hash_workload_source(a), hash_workload_source(b))

    def test_volatile_metadata_does_not_change_hash(self):
        from gefyra.bridge_mount.carrier2mount.source_hash import hash_workload_source

        a = _make_deployment()
        b = deepcopy(a)
        # These fields get set/bumped by the apiserver on every read and must
        # not affect the logical "what is this workload" hash.
        b.metadata.resource_version = "999"
        b.metadata.uid = "fresh-uid"
        b.metadata.generation = 17
        self.assertEqual(hash_workload_source(a), hash_workload_source(b))

    def test_hash_is_stable_string(self):
        from gefyra.bridge_mount.carrier2mount.source_hash import hash_workload_source

        h = hash_workload_source(_make_deployment())
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)  # sha256 hex


class TestHpaHash(TestCase):
    def test_identical_hpas_hash_identically(self):
        from gefyra.bridge_mount.carrier2mount.source_hash import hash_hpa_source

        self.assertEqual(hash_hpa_source(_make_hpa()), hash_hpa_source(_make_hpa()))

    def test_scale_target_name_is_ignored(self):
        """The duplicated HPA always retargets the shadow workload — so the
        source-hash must ignore scaleTargetRef.name, else the hash would
        always mismatch between original and duplicate."""
        from gefyra.bridge_mount.carrier2mount.source_hash import hash_hpa_source

        a = _make_hpa(target_name="nginx")
        b = _make_hpa(target_name="nginx-gefyra")
        self.assertEqual(hash_hpa_source(a), hash_hpa_source(b))

    def test_min_replicas_change_changes_hash(self):
        from gefyra.bridge_mount.carrier2mount.source_hash import hash_hpa_source

        a = _make_hpa(min_replicas=1)
        b = _make_hpa(min_replicas=3)
        self.assertNotEqual(hash_hpa_source(a), hash_hpa_source(b))

    def test_max_replicas_change_changes_hash(self):
        from gefyra.bridge_mount.carrier2mount.source_hash import hash_hpa_source

        a = _make_hpa(max_replicas=5)
        b = _make_hpa(max_replicas=10)
        self.assertNotEqual(hash_hpa_source(a), hash_hpa_source(b))
