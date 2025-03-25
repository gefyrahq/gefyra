import yaml

from typing import Optional
from pydantic import ConfigDict, Field, BaseModel

from gefyra.bridge.carrier2.utils import reload_carrier2_config, send_carrier2_config


ERROR_LOG_PATH = "/tmp/carrier.error.log"


class CarrierMatchHeader(BaseModel):
    name: str
    value: str


class CarrierMatch(BaseModel):
    match_header: CarrierMatchHeader = Field(
        serialization_alias="matchHeader",
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

    def commit(self, pod_name: str, namespace: str):
        send_carrier2_config(pod_name, namespace, self.model_dump_yaml())
        reload_carrier2_config(pod_name, namespace)
