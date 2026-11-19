import pytest

from tests.conftest import purge_gefyra_objects


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if (
        call.when != "call"
        or not report.failed
        or item.module.__name__ != "tests.e2e.test_bridge"
    ):
        return

    operator = item.funcargs.get("operator")
    if operator is None:
        return

    try:
        logs = operator.kubectl(
            ["logs", "-n", "default", "deployment/nginx-deployment"],
            as_dict=False,
        )
    except RuntimeError as error:
        logs = f"Could not retrieve nginx-deployment logs: {error}"
    report.sections.append(("nginx-deployment logs", logs))


@pytest.fixture(scope="class", autouse=True)
def clear_gefyra_clients(operator):
    yield
    purge_gefyra_objects(operator)
