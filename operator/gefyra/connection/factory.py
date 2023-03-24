from enum import Enum
from typing import List, Optional

from gefyra.configuration import OperatorConfiguration
from gefyra.connection.abstract import AbstractGefyraConnectionProvider
from gefyra.connection.stowaway import StowawayBuilder


class ProviderType(Enum):
    STOWAWAY = "stowaway"


class GefyraConnectionFactory:
    def __init__(self):
        self._builders = {}

    def register_builder(self, provider_type: ProviderType, builder):
        self._builders[provider_type.value] = builder

    def __create(
        self,
        provider_type: ProviderType,
        configuration: OperatorConfiguration,
        logger,
        **kwargs
    ):
        builder = self._builders.get(provider_type.value)
        if not builder:
            raise ValueError(provider_type)
        return builder(configuration, logger, **kwargs)

    def get(
        self,
        provider_type: ProviderType,
        configuration: OperatorConfiguration,
        logger,
        **kwargs
    ) -> AbstractGefyraConnectionProvider:
        return self.__create(
            provider_type, configuration, logger, **kwargs
        )


connection_provider_factory = GefyraConnectionFactory()
connection_provider_factory.register_builder(ProviderType.STOWAWAY, StowawayBuilder())
