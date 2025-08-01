from pathlib import Path
from pytest_kubernetes.providers import AClusterManager


def test_a_write_client_file(operator: AClusterManager):
    k3d = operator
    k3d.kubeconfig
    from gefyra.api.mount import mount

    file_path = str(
        Path(Path(__file__).parent.parent, "fixtures/nginx.yaml").absolute()
    )
    operator.apply(file_path)

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
