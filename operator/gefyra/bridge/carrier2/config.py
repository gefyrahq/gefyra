from functools import partial
import yaml

from typing import Optional
from pydantic import ConfigDict, Field, BaseModel

import kubernetes as k8s

from gefyra.bridge.carrier2.utils import (
    stream_exec,
)
from gefyra.utils import wait_until_condition


ERROR_LOG_PATH = "/tmp/carrier.error.log"


class CarrierMatchHeader(BaseModel):
    name: str
    value: str


class CarrierMatch(BaseModel):
    match_header: CarrierMatchHeader = Field(
        alias="matchHeader",
    )


class CarrierRule(BaseModel):
    match: list[CarrierMatch]


class CarrierBridge(BaseModel):
    endpoint: str
    rules: list[CarrierRule]


class CarrierProbe(BaseModel):
    httpGet: list[int]


class CarrierTLS(BaseModel):
    certificate: str = "./tests/fixtures/test_cert.pem"
    key: str = "./tests/fixtures/test_key.pem"
    sni: Optional[str] = None


class Carrier2Config(BaseModel):
    version: int = 1
    threads: int = 4
    port: Optional[int] = None
    error_log: str = Field(
        default=ERROR_LOG_PATH,
    )
    pid_file: str = "/tmp/carrier2.pid"
    upgrade_sock: str = "/tmp/carrier2.sock"
    upstream_keepalive_pool_size: int = 100
    tls: Optional[CarrierTLS] = None
    clusterUpstream: Optional[list[str]] = None
    probes: Optional[CarrierProbe] = None
    bridges: Optional[dict[str, CarrierBridge]] = None
    model_config = ConfigDict(coerce_numbers_to_str=True)

    def model_dump_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(by_alias=True, exclude_none=True), sort_keys=False
        )

    def commit(self, pod_name: str, container_name: str, namespace: str):

        core_v1 = k8s.client.CoreV1Api()
        read_func = partial(core_v1.read_namespaced_pod_status, pod_name, namespace)

        # busy wait for pod to get ready, raises RuntimeError on timeout
        # TODO raise TemporaryError to handle longer pulls via async
        wait_until_condition(
            read_func,
            lambda s: all(
                [container.ready for container in s.status.container_statuses]
            ),
            timeout=30,
            backoff=0.2,
        )

        config_str = self.model_dump_yaml()

        config_commands = [
            # 1. write new config
            "cat <<'EOF' > /tmp/config.yaml\n" f"{config_str}",
            "EOF",
            # 2. graceful upgrade of the process
            "kill -SIGQUIT $(ps | grep '[c]arrier2' | awk ' { print $1 }' | tail -1) && "
            "carrier2 -c /tmp/config.yaml -u &",
            # 3. read current config
            "cat /tmp/config.yaml",
        ]

        read_func = partial(
            stream_exec, pod_name, namespace, container_name, config_commands
        )
        # TODO raise TemporaryError to handle longer Carrier2 pulls via async
        wait_until_condition(
            read_func,
            lambda s: isinstance(s, str) and config_str in s,
            timeout=30,
            backoff=1,
        )
