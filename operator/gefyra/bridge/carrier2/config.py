import yaml

from typing import Optional, Tuple, Type
from pydantic import Field, BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


ERROR_LOG_PATH = "error.log"


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
    certificate: str
    key: str
    sni: Optional[str] = None


class CarrierConfig(BaseSettings):
    version: str
    threads: int
    port: int
    error_log: str = Field(
        default=ERROR_LOG_PATH,
    )
    tls: Optional[CarrierTLS]
    clusterUpstream: Optional[list[str]]
    probes: Optional[CarrierProbe]
    bridges: Optional[dict[str, CarrierBridge]]
    model_config = SettingsConfigDict(
        yaml_file="/tmp/config.yaml", coerce_numbers_to_str=True
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (YamlConfigSettingsSource(settings_cls),)

    def model_dump_yaml(self) -> str:
        return yaml.safe_dump(self.model_dump(), sort_keys=False)
