from pytest_kubernetes.providers import AClusterManager


def test_a_create_client(operator: AClusterManager):
    operator.apply("tests/fixtures/a_gefyra_client.yaml")