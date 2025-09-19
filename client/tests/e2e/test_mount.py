from pathlib import Path
import pytest
from pytest_kubernetes.providers import AClusterManager


@pytest.fixture
def workloads_for_test(operator):
    file_path = str(
        Path(Path(__file__).parent.parent, "fixtures/nginx.yaml").absolute()
    )
    operator.apply(file_path)
    yield
    operator.kubectl(["delete", "-f", file_path], as_dict=False)


def test_a_create_simple_mount(operator: AClusterManager, workloads_for_test):
    k3d = operator
    k3d.kubeconfig
    from gefyra.api.mount import mount

    res = mount(
        namespace="default",
        target="deploy/nginx-deployment/nginx",
        provider="carrier2",
        kubeconfig=k3d.kubeconfig,
        kubecontext=k3d.context,
        wait=True,
        timeout=120,
    )

    assert res is True
