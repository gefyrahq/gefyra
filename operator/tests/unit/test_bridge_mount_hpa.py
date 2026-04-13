import logging
from unittest import TestCase
from unittest.mock import MagicMock, patch


logger = logging.getLogger(__name__)


def _make_hpa(
    name: str = "nginx-hpa",
    target_kind: str = "Deployment",
    target_name: str = "nginx-deployment",
    labels: dict | None = None,
    annotations: dict | None = None,
):
    from kubernetes.client import (
        V1ObjectMeta,
        V2CrossVersionObjectReference,
        V2HorizontalPodAutoscaler,
        V2HorizontalPodAutoscalerSpec,
        V2HorizontalPodAutoscalerStatus,
    )

    return V2HorizontalPodAutoscaler(
        metadata=V1ObjectMeta(
            name=name,
            namespace="default",
            labels=labels or {"app": "nginx"},
            annotations=annotations,
            uid="orig-uid",
            resource_version="42",
            generation=3,
        ),
        spec=V2HorizontalPodAutoscalerSpec(
            scale_target_ref=V2CrossVersionObjectReference(
                api_version="apps/v1",
                kind=target_kind,
                name=target_name,
            ),
            min_replicas=1,
            max_replicas=5,
        ),
        status=V2HorizontalPodAutoscalerStatus(
            current_replicas=1,
            desired_replicas=1,
            conditions=[],
        ),
    )


class TestGenerateDuplicateHpaName(TestCase):
    def test_short_name_appends_suffix(self):
        from gefyra.bridge_mount.utils import generate_duplicate_hpa_name

        self.assertEqual(generate_duplicate_hpa_name("nginx"), "nginx-gefyra")

    def test_long_name_truncates_to_63_chars(self):
        from gefyra.bridge_mount.utils import generate_duplicate_hpa_name

        long_name = "a" * 80
        result = generate_duplicate_hpa_name(long_name)
        self.assertLessEqual(len(result), 63)
        self.assertTrue(result.endswith("-gefyra"))


class TestCloneHpaForShadow(TestCase):
    def test_clone_redirects_to_shadow_workload(self):
        from gefyra.bridge_mount.carrier2mount.hpa import (
            DUPLICATION_ID_LABEL,
            clone_hpa_for_shadow,
        )

        original = _make_hpa(
            annotations={
                "kubectl.kubernetes.io/last-applied-configuration": "{}",
                "autoscaling.alpha.kubernetes.io/metrics": "ignored",
                "user.example.com/keep": "yes",
            },
        )
        labels = {"app": "nginx-gefyra", DUPLICATION_ID_LABEL: "abc-123"}

        cloned = clone_hpa_for_shadow(
            original_hpa=original,
            shadow_workload_name="nginx-deployment-gefyra",
            duplication_labels=labels,
        )

        self.assertEqual(cloned.metadata.name, "nginx-hpa-gefyra")
        self.assertEqual(
            cloned.spec.scale_target_ref.name, "nginx-deployment-gefyra"
        )
        self.assertEqual(cloned.spec.scale_target_ref.kind, "Deployment")
        self.assertEqual(cloned.metadata.labels, labels)
        self.assertIsNone(cloned.metadata.uid)
        self.assertIsNone(cloned.metadata.resource_version)
        self.assertIsNone(cloned.metadata.generation)
        self.assertIsNone(cloned.status)
        self.assertIn("user.example.com/keep", cloned.metadata.annotations)
        self.assertNotIn(
            "kubectl.kubernetes.io/last-applied-configuration",
            cloned.metadata.annotations,
        )
        self.assertNotIn(
            "autoscaling.alpha.kubernetes.io/metrics",
            cloned.metadata.annotations,
        )
        # Original is not mutated
        self.assertEqual(original.metadata.uid, "orig-uid")
        self.assertEqual(original.spec.scale_target_ref.name, "nginx-deployment")


class TestFindHpaForTarget(TestCase):
    def test_returns_match(self):
        from kubernetes.client import V2HorizontalPodAutoscalerList

        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import find_hpa_for_target

            match = _make_hpa()
            mock_api.return_value.list_namespaced_horizontal_pod_autoscaler.return_value = (
                V2HorizontalPodAutoscalerList(items=[match])
            )
            result = find_hpa_for_target(
                "default", "Deployment", "nginx-deployment", logger
            )
            self.assertIs(result, match)

    def test_returns_none_when_no_match(self):
        from kubernetes.client import V2HorizontalPodAutoscalerList

        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import find_hpa_for_target

            mock_api.return_value.list_namespaced_horizontal_pod_autoscaler.return_value = (
                V2HorizontalPodAutoscalerList(
                    items=[_make_hpa(target_name="other")]
                )
            )
            self.assertIsNone(
                find_hpa_for_target(
                    "default", "Deployment", "nginx-deployment", logger
                )
            )

    def test_kind_match_is_case_insensitive(self):
        from kubernetes.client import V2HorizontalPodAutoscalerList

        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import find_hpa_for_target

            match = _make_hpa(target_kind="deployment")
            mock_api.return_value.list_namespaced_horizontal_pod_autoscaler.return_value = (
                V2HorizontalPodAutoscalerList(items=[match])
            )
            result = find_hpa_for_target(
                "default", "Deployment", "nginx-deployment", logger
            )
            self.assertIs(result, match)

    def test_multiple_matches_warns_and_returns_first(self):
        from kubernetes.client import V2HorizontalPodAutoscalerList

        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import find_hpa_for_target

            first = _make_hpa(name="hpa-a")
            second = _make_hpa(name="hpa-b")
            mock_api.return_value.list_namespaced_horizontal_pod_autoscaler.return_value = (
                V2HorizontalPodAutoscalerList(items=[first, second])
            )
            warn_logger = MagicMock()
            result = find_hpa_for_target(
                "default", "Deployment", "nginx-deployment", warn_logger
            )
            self.assertIs(result, first)
            warn_logger.warning.assert_called_once()

    def test_api_error_returns_none(self):
        from kubernetes.client import ApiException

        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import find_hpa_for_target

            mock_api.return_value.list_namespaced_horizontal_pod_autoscaler.side_effect = (
                ApiException(status=403, reason="Forbidden")
            )
            warn_logger = MagicMock()
            result = find_hpa_for_target(
                "default", "Deployment", "nginx-deployment", warn_logger
            )
            self.assertIsNone(result)
            warn_logger.warning.assert_called_once()


class TestApplyClonedHpa(TestCase):
    def test_create_path(self):
        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import apply_cloned_hpa

            cloned = _make_hpa(name="nginx-hpa-gefyra")
            apply_cloned_hpa("default", cloned)
            mock_api.return_value.create_namespaced_horizontal_pod_autoscaler.assert_called_once_with(
                namespace="default", body=cloned
            )

    def test_409_falls_back_to_patch(self):
        from kubernetes.client import ApiException

        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import apply_cloned_hpa

            cloned = _make_hpa(name="nginx-hpa-gefyra")
            api = mock_api.return_value
            api.create_namespaced_horizontal_pod_autoscaler.side_effect = (
                ApiException(status=409)
            )
            apply_cloned_hpa("default", cloned)
            api.patch_namespaced_horizontal_pod_autoscaler.assert_called_once_with(
                name="nginx-hpa-gefyra", namespace="default", body=cloned
            )


class TestDeleteDuplicatedHpa(TestCase):
    def test_delete_by_name_then_label_sweep(self):
        from kubernetes.client import V2HorizontalPodAutoscalerList

        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import (
                DUPLICATION_ID_LABEL,
                delete_duplicated_hpa,
            )

            api = mock_api.return_value
            api.list_namespaced_horizontal_pod_autoscaler.return_value = (
                V2HorizontalPodAutoscalerList(items=[])
            )
            delete_duplicated_hpa("default", "nginx-hpa", "abc-123", logger)
            api.delete_namespaced_horizontal_pod_autoscaler.assert_called_once_with(
                name="nginx-hpa-gefyra", namespace="default"
            )
            api.list_namespaced_horizontal_pod_autoscaler.assert_called_once_with(
                namespace="default",
                label_selector=f"{DUPLICATION_ID_LABEL}=abc-123",
            )

    def test_404_on_direct_delete_is_ignored(self):
        from kubernetes.client import ApiException, V2HorizontalPodAutoscalerList

        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import delete_duplicated_hpa

            api = mock_api.return_value
            api.delete_namespaced_horizontal_pod_autoscaler.side_effect = (
                ApiException(status=404)
            )
            api.list_namespaced_horizontal_pod_autoscaler.return_value = (
                V2HorizontalPodAutoscalerList(items=[])
            )
            delete_duplicated_hpa("default", "nginx-hpa", "abc-123", logger)

    def test_label_sweep_deletes_leftovers(self):
        from kubernetes.client import V2HorizontalPodAutoscalerList

        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import delete_duplicated_hpa

            api = mock_api.return_value
            leftover = _make_hpa(name="leftover-gefyra")
            api.list_namespaced_horizontal_pod_autoscaler.return_value = (
                V2HorizontalPodAutoscalerList(items=[leftover])
            )
            delete_duplicated_hpa("default", None, "abc-123", logger)
            api.delete_namespaced_horizontal_pod_autoscaler.assert_called_once_with(
                name="leftover-gefyra", namespace="default"
            )

    def test_no_duplication_id_skips_label_sweep(self):
        with patch(
            "gefyra.bridge_mount.carrier2mount.hpa._autoscaling_api"
        ) as mock_api:
            from gefyra.bridge_mount.carrier2mount.hpa import delete_duplicated_hpa

            api = mock_api.return_value
            delete_duplicated_hpa("default", "nginx-hpa", None, logger)
            api.list_namespaced_horizontal_pod_autoscaler.assert_not_called()
