from enum import Enum

from gefyra.configuration import OperatorConfiguration
from gefyra.bridgemount.abstract import AbstractGefyraBridgeMountProvider
from gefyra.bridgemount.duplicate import DuplicateBuilder


class ShadowProviderType(Enum):
    DUPLICATE = "duplicate"


class GefyraShadowFactory:
    def __init__(self):
        self._builders = {}

    def register_builder(self, provider_type: ShadowProviderType, builder):
        self._builders[provider_type.value] = builder

    def __create(
        self,
        provider_type: ShadowProviderType,
        configuration: OperatorConfiguration,
        target_namespace: str,
        target: str,
        target_container: str,
        logger,
        **kwargs
    ):
        builder = self._builders.get(provider_type.value)
        if not builder:
            raise ValueError(provider_type)
        return builder(
            configuration, target_namespace, target, target_container, logger, **kwargs
        )

    def get(
        self,
        provider_type: ShadowProviderType,
        configuration: OperatorConfiguration,
        target_namespace: str,
        target_pod: str,
        target_container: str,
        logger,
        **kwargs
    ) -> AbstractGefyraBridgeMountProvider:
        return self.__create(
            provider_type,
            configuration,
            target_namespace,
            target_pod,
            target_container,
            logger,
            **kwargs
        )


shadow_provider_factory = GefyraShadowFactory()
shadow_provider_factory.register_builder(
    ShadowProviderType.DUPLICATE, DuplicateBuilder()
)
