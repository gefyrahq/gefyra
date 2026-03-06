import asyncio
from enum import StrEnum
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


class CarrierMatchType(StrEnum):
    ExactLookup = "exact"
    PrefixLookup = "prefix"
    RegexLookup = "regex"


class CarrierHeaderMatch(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    name: str
    value: str
    type: CarrierMatchType = Field(
        default=CarrierMatchType.ExactLookup, validate_default=True
    )


class CarrierPathMatch(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    path: str
    type: CarrierMatchType = Field(
        default=CarrierMatchType.ExactLookup, validate_default=True
    )


class CarrierMatchHeader(BaseModel):
    match_header: CarrierHeaderMatch = Field(
        alias="matchHeader",
    )


class CarrierMatchPath(BaseModel):
    match_path: CarrierPathMatch = Field(
        alias="matchPath",
    )


class CarrierRule(BaseModel):
    match: list[CarrierMatchHeader | CarrierMatchPath]


class CarrierBridge(BaseModel):
    endpoint: str
    rules: list[CarrierRule]


class CarrierProbe(BaseModel):
    httpGet: list[int] = []
    httpsGet: list[int] = []


class CarrierTLS(BaseModel):
    certificate: str = "./tests/fixtures/test_cert.pem"
    key: str = "./tests/fixtures/test_key.pem"
    sni: Optional[str] = None


class Carrier2Proxy(BaseModel):
    port: Optional[int] = None
    tls: Optional[CarrierTLS] = None
    clusterUpstream: Optional[list[str]] = None
    bridges: dict[str, CarrierBridge] = {}


class Carrier2Config(BaseModel):
    version: int = 1
    threads: int = 4
    error_log: str = Field(
        default=ERROR_LOG_PATH,
    )
    pid_file: str = "/tmp/carrier2.pid"
    upgrade_sock: str = "/tmp/carrier2.sock"
    upstream_keepalive_pool_size: int = 100
    probes: Optional[CarrierProbe] = None
    proxy: List[Carrier2Proxy] = []

    model_config = ConfigDict(coerce_numbers_to_str=True, use_enum_values=True)

    def model_dump_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(by_alias=True, exclude_none=True), sort_keys=False
        )

    async def commit(
        self,
        logger,
        pod_name: str,
        container_name: str,
        namespace: str,
        debug: bool = False,
    ):
        core_v1 = k8s.client.CoreV1Api()
        read_func = partial(core_v1.read_namespaced_pod_status, pod_name, namespace)

        # busy wait for pod to get ready, raises RuntimeError on timeout
        # TODO raise TemporaryError to handle longer pulls via async
        await asyncio.to_thread(
            wait_until_condition,
            read_func,
            lambda s: all(
                [container.started for container in s.status.container_statuses]
            ),
            timeout=120,
            backoff=2,
        )

        config_str = self.model_dump_yaml()

        config_commands = [
            # 1. write new config
            f"cat <<'EOF' > /tmp/config.yaml\n{config_str}",
            "EOF",
            # 2. graceful upgrade of the process
            RELOAD_CARRIER2_DEBUG if debug else RELOAD_CARRIER2_INFO,
            # 3. read current log
            f"cat {ERROR_LOG_PATH}",
        ]

        def _check_carrier2_output(s):
            return (
                isinstance(s, str)
                and "Bootstrap starting" in s
                and "thread 'main' panicked" not in s
            )

        read_func = partial(
            stream_exec_retries,
            logger,
            pod_name,
            namespace,
            container_name,
            config_commands,
            10,
            _check_carrier2_output,
        )

        # TODO raise TemporaryError to handle longer Carrier2 pulls via async
        await asyncio.to_thread(
            wait_until_condition,
            read_func,
            _check_carrier2_output,
            timeout=30,
            backoff=2,
        )

    @classmethod
    def from_string(cls, content_str: str):
        return Carrier2Config(**yaml.safe_load(content_str))

    async def add_bridge_rules_for_mount(
        self,
        bridge_mount_name: str,
        namespace: str,
        current_bridge_add: str | None,
        current_bridge_rm: str | None,
    ) -> "Carrier2Config":
        custom_object_api = k8s.client.CustomObjectsApi()
        bridges = await asyncio.to_thread(
            custom_object_api.list_namespaced_custom_object,
            "gefyra.dev",
            "v1",
            namespace,
            "gefyrabridges",
            label_selector=f"gefyra.dev/bridge-mount={bridge_mount_name}",
        )
        logger.debug(f"gefyra.dev/bridge-mount={bridge_mount_name}")
        logger.debug(f"BRIDGES {bridges}")

        for bridge in bridges["items"]:
            logger.debug(f"BRIDGE State {bridge['state']}")
            bridge_name = bridge["metadata"]["name"]
            if bridge_name == current_bridge_rm:
                # exclude this bridge from the full configuration as it is about to be removed
                continue
            if bridge["portMappings"]:
                rport = -1
                try:
                    for port in bridge["portMappings"]:
                        rport = int(port.split(":")[1])
                        proxy_idx = next(
                            (
                                index
                                for (index, d) in enumerate(self.proxy)
                                if d.port == rport
                            ),
                            None,
                        )
                        if proxy_idx is None:
                            raise BridgeInstallException(
                                f"No proxy found that serves port '{rport}'"
                            )
                        if self.proxy[proxy_idx].bridges:
                            self.proxy[proxy_idx].bridges.update(
                                {
                                    bridge_name: self._convert_bridge_to_rule(
                                        bridge, rport
                                    )
                                }
                            )
                        else:
                            self.proxy[proxy_idx].bridges = {
                                bridge_name: self._convert_bridge_to_rule(bridge, rport)
                            }
                except Exception as e:
                    if current_bridge_add and bridge_name == current_bridge_add:
                        raise BridgeInstallException(
                            f"Could not install GefyraBridge: {e}"
                        ) from None
                    else:
                        continue
        return self

    def _convert_bridge_to_rule(self, bridge: dict, target_port: int) -> CarrierBridge:
        return CarrierBridge(
            endpoint=bridge["clusterEndpoint"][str(target_port)],
            rules=self._get_rules_for_bridge(bridge),
        )

    def _get_rules_for_bridge(self, bridge: dict) -> List[CarrierRule]:
        rules = []
        for rule in bridge["providerParameter"]["rules"]:
            if "match" in rule:
                rules.append(CarrierRule(**rule))
        return rules
