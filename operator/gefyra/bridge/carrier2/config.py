from functools import partial
import logging
import yaml

from typing import List, Optional
from pydantic import ConfigDict, Field, BaseModel

import kubernetes as k8s

from gefyra.bridge.carrier2.utils import (
    stream_exec_retries,
)
from gefyra.utils import wait_until_condition
from gefyra.bridge.carrier2.const import RELOAD_CARRIER2_DEBUG, RELOAD_CARRIER2_INFO
from gefyra.bridge.exceptions import BridgeInstallException


logger = logging.getLogger(__name__)

ERROR_LOG_PATH = "/tmp/carrier.log"


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

    def commit(
        self, pod_name: str, container_name: str, namespace: str, debug: bool = False
    ):
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
            RELOAD_CARRIER2_DEBUG if debug else RELOAD_CARRIER2_INFO,
            # 3. read current log
            f"cat {ERROR_LOG_PATH}",
        ]

        read_func = partial(
            stream_exec_retries,
            pod_name,
            namespace,
            container_name,
            config_commands,
            10,
        )

        # TODO raise TemporaryError to handle longer Carrier2 pulls via async
        def _check_carrier2_output(s):
            return (
                isinstance(s, str)
                and "Daemonizing the server" in s
                and "thread 'main' panicked" not in s
            )

        wait_until_condition(
            read_func,
            _check_carrier2_output,
            timeout=30,
            backoff=1,
        )

    @classmethod
    def from_string(cls, content_str: str):
        return Carrier2Config(**yaml.safe_load(content_str))

    def add_bridge_rules_for_mount(
        self, bridge_mount_name: str, namespace: str
    ) -> "Carrier2Config":
        custom_object_api = k8s.client.CustomObjectsApi()
        bridges = custom_object_api.list_namespaced_custom_object(
            "gefyra.dev",
            "v1",
            namespace,
            "gefyrabridges",
            label_selector=f"gefyra.dev/bridge-mount={bridge_mount_name}",
        )
        logger.debug(f"gefyra.dev/bridge-mount={bridge_mount_name}")
        logger.debug(f"BRIDGES {bridges}")

        result = {}
        for bridge in bridges["items"]:
            logger.info(f"BRIDGE State {bridge['state']}")
            if bridge["state"] != "REMOVING":
                bridge_name = bridge["metadata"]["name"]
                result[bridge_name] = self._convert_bridge_to_rule(bridge)
        self.bridges = result
        return self

    def _convert_bridge_to_rule(self, bridge: dict) -> CarrierBridge:
        return CarrierBridge(
            endpoint=bridge["clusterEndpoint"],
            rules=self._get_rules_for_bridge(bridge),
        )

    def _get_rules_for_bridge(self, bridge: dict) -> List[CarrierRule]:
        rules = []
        logger.info(bridge)
        for rule in bridge["providerParameter"]["rules"]:
            logger.info(rule)
            if "match" in rule:
                rules.append(CarrierRule(**rule))
        return rules
