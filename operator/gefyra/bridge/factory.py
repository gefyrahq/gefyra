from enum import Enum
from typing import Callable

from gefyra.configuration import OperatorConfiguration
from gefyra.bridge.abstract import AbstractGefyraBridgeProvider
from gefyra.bridge.carrier import CarrierBuilder
from gefyra.bridge.carrier2 import Carrier2Builder


class BridgeProviderType(Enum):
    CARRIER = "carrier"
    CARRIER2 = "carrier2"


class GefyraBridgeFactory:
    def __init__(self):
        self._builders = {}

    def register_builder(self, provider_type: BridgeProviderType, builder):
        self._builders[provider_type.value] = builder

    def __create(
        self,
        provider_type: BridgeProviderType,
        configuration: OperatorConfiguration,
        name: str,
        target_namespace: str,
        target_pod: str,
        target_container: str,
        post_event_function: Callable[[str, str, str], None],
        logger,
        **kwargs
    ):
        builder = self._builders.get(provider_type.value)
        if not builder:
            raise ValueError(provider_type)
        return builder(
            configuration,
            name,
            target_namespace,
            target_pod,
            target_container,
            post_event_function,
            logger,
            **kwargs
        )

    def get(
        self,
        provider_type: BridgeProviderType,
        configuration: OperatorConfiguration,
        name: str,
        target_namespace: str,
        target_pod: str,
        target_container: str,
        post_event_function: Callable[[str, str, str], None],
        logger,
        **kwargs
    ) -> AbstractGefyraBridgeProvider:
        return self.__create(
            provider_type,
            configuration,
            name,
            target_namespace,
            target_pod,
            target_container,
            post_event_function,
            logger,
            **kwargs
        )


bridge_provider_factory = GefyraBridgeFactory()
bridge_provider_factory.register_builder(BridgeProviderType.CARRIER, CarrierBuilder())
bridge_provider_factory.register_builder(BridgeProviderType.CARRIER2, Carrier2Builder())
