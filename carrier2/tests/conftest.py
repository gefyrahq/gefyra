import multiprocessing
import os
import signal
import subprocess
from typing import Optional
import pytest


@pytest.fixture(scope="session")
def carrier2(request):
    name = "RUST_LOG=debug ./target/release/carrier2"
    subprocess.run(
        (f"cargo build --release"),
        shell=True,
    )

    def call_with_args(
        args: str, timeout: int = 1, queue: Optional[multiprocessing.Queue] = None
    ) -> str:
        try:
            p = subprocess.Popen(
                f"{name} {args}",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            p.wait(timeout=timeout)
            stdout = p.stdout.read().decode("utf-8")
            if queue:
                queue.put(stdout)
            else:
                return stdout
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            stdout = p.stdout.read().decode("utf-8")
            if queue:
                queue.put(stdout)
            else:
                return stdout

    yield call_with_args
