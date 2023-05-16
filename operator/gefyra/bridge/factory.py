from enum import Enum

from gefyra.configuration import OperatorConfiguration
from gefyra.bridge.abstract import AbstractGefyraBridgeProvider
from gefyra.bridge.carrier import CarrierBuilder


class BridgeProviderType(Enum):
    CARRIER = "carrier"


class GefyraBridgeFactory:
    def __init__(self):
        self._builders = {}

    def register_builder(self, provider_type: BridgeProviderType, builder):
        self._builders[provider_type.value] = builder

    def __create(
        self,
        provider_type: BridgeProviderType,
        configuration: OperatorConfiguration,
        target_namespace: str,
        target_pod: str,
        target_container: str,
        logger,
        **kwargs
    ):
        builder = self._builders.get(provider_type.value)
        if not builder:
            raise ValueError(provider_type)
        return builder(
            configuration,
            target_namespace,
            target_pod,
            target_container,
            logger,
            **kwargs
        )

    def get(
        self,
        provider_type: BridgeProviderType,
        configuration: OperatorConfiguration,
        target_namespace: str,
        target_pod: str,
        target_container: str,
        logger,
        **kwargs
    ) -> AbstractGefyraBridgeProvider:
        return self.__create(
            provider_type,
            configuration,
            target_namespace,
            target_pod,
            target_container,
            logger,
            **kwargs
        )


bridge_provider_factory = GefyraBridgeFactory()
bridge_provider_factory.register_builder(BridgeProviderType.CARRIER, CarrierBuilder())
