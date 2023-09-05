import sys
import platform
from pathlib import Path
import subprocess
import pytest
from .utils import GefyraDockerClient


@pytest.fixture(scope="session")
def cargo_image(request):
    name = "cargo:pytest"
    if sys.platform == "win32" or "microsoft-standard" in platform.release():
        target = "cargo-win"
    else:
        target = "cargo"
    subprocess.run(
        (
            f"docker build --target {target} -t {name} -f"
            f" {(Path(__file__).parent / Path('../../../cargo/Dockerfile')).resolve()}"
            f" {(Path(__file__).parent / Path('../../../cargo/')).resolve()}"
        ),
        shell=True,
    )
    request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
    return name


@pytest.fixture(scope="session")
def gclient_a(cargo_image):
    c = GefyraDockerClient("gclient-a")
    yield c
    try:
        c.delete()
    except Exception:
        pass


@pytest.fixture(scope="session")
def gclient_b():
    c = GefyraDockerClient("gclient-b")
    yield c
    try:
        c.delete()
    except Exception:
        pass
