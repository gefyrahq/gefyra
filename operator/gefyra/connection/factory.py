from enum import Enum

from gefyra.configuration import OperatorConfiguration
from gefyra.connection.abstract import AbstractGefyraConnectionProvider
from gefyra.connection.stowaway import StowawayBuilder


class ConnectionProviderType(Enum):
    STOWAWAY = "stowaway"


class GefyraConnectionFactory:
    def __init__(self):
        self._builders = {}

    def register_builder(self, provider_type: ConnectionProviderType, builder):
        self._builders[provider_type.value] = builder

    def __create(
        self,
        provider_type: ConnectionProviderType,
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
        provider_type: ConnectionProviderType,
        configuration: OperatorConfiguration,
        logger,
        **kwargs
    ) -> AbstractGefyraConnectionProvider:
        return self.__create(provider_type, configuration, logger, **kwargs)


connection_provider_factory = GefyraConnectionFactory()
connection_provider_factory.register_builder(
    ConnectionProviderType.STOWAWAY, StowawayBuilder()
)
