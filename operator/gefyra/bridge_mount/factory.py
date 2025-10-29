from enum import Enum

from gefyra.configuration import OperatorConfiguration
from gefyra.bridge_mount.abstract import AbstractGefyraBridgeMountProvider
from gefyra.bridge_mount.duplicate import DuplicateBridgeMount
from gefyra.bridge_mount.duplicate.builder import DuplicateBuilder


class BridgeMountProviderType(Enum):
    DUPLICATE = "duplicate"


class GefyraBridgeMountFactory:
    def __init__(self):
        self._builders = {}

    def register_builder(self, provider_type: BridgeMountProviderType, builder):
        self._builders[provider_type.value] = builder

    def __create(
        self,
        provider_type: BridgeMountProviderType,
        configuration: OperatorConfiguration,
        name: str,
        target_namespace: str,
        target: str,
        target_container: str,
        post_event_function: callable,
        parameter: dict,
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
            target,
            target_container,
            post_event_function,
            parameter,
            logger,
            **kwargs
        )

    def get(
        self,
        provider_type: BridgeMountProviderType,
        configuration: OperatorConfiguration,
        name: str,
        target_namespace: str,
        target: str,
        target_container: str,
        post_event_function: callable,
        parameter: dict,
        logger,
        **kwargs
    ) -> AbstractGefyraBridgeMountProvider:
        return self.__create(
            provider_type,
            configuration,
            name,
            target_namespace,
            target,
            target_container,
            post_event_function,
            parameter,
            logger,
            **kwargs
        )


bridge_mount_provider_factory = GefyraBridgeMountFactory()
bridge_mount_provider_factory.register_builder(
    BridgeMountProviderType.DUPLICATE, DuplicateBuilder()
)
