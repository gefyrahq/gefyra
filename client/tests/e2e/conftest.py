import pytest
from tests.conftest import purge_gefyra_objects


@pytest.fixture(scope="class", autouse=True)
def clear_gefyra_clients(operator):
    yield
    purge_gefyra_objects(operator)
