from abc import ABC, abstractmethod


class AbstractGefyraBridgeMountProvider(ABC):
    """The Gefyra shadow provider"""

    provider_type = ""

    @abstractmethod
    async def install(self) -> None:
        """
        Install this Gefyra bridgemount provider to the Kubernetes Resource
        """
        raise NotImplementedError

    @abstractmethod
    async def prepare(self) -> None:
        """
        Prepare this Gefyra bridgemount provider to the Kubernetes Resource
        """
        raise NotImplementedError

    @abstractmethod
    async def ready(self) -> bool:
        """
        Check if this Gefyra bridgemount provider is ready for bridgemounts
        """
        raise NotImplementedError

    @abstractmethod
    async def prepared(self) -> bool:
        """
        Check if this Gefyra bridgemount provider is prepared for bridgemounts
        """
        raise NotImplementedError

    @abstractmethod
    async def uninstall(self) -> None:
        """
        Uninstall this Gefyra bridgemount provider from the Kubernetes Pod
        """
        raise NotImplementedError

    @abstractmethod
    async def target_exists(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def validate(self, bridge_request: dict, hits: dict | None):
        """
        Validate the bridgemount request
        """
        raise NotImplementedError
