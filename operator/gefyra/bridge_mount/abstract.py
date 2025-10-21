from abc import ABC, abstractmethod


class AbstractGefyraBridgeMountProvider(ABC):
    """The Gefyra shadow provider"""

    provider_type = ""

    @abstractmethod
    def install(self) -> None:
        """
        Install this Gefyra bridgemount provider to the Kubernetes Resource
        """
        raise NotImplementedError

    @abstractmethod
    def prepare(self) -> None:
        """
        Prepare this Gefyra bridgemount provider to the Kubernetes Resource
        """
        raise NotImplementedError

    @abstractmethod
    def ready(self) -> bool:
        """
        Check if this Gefyra bridgemount provider is ready for bridgemounts
        """
        raise NotImplementedError

    @abstractmethod
    def prepared(self) -> bool:
        """
        Check if this Gefyra bridgemount provider is prepared for bridgemounts
        """
        raise NotImplementedError

    @abstractmethod
    def uninstall(self) -> None:
        """
        Uninstall this Gefyra bridgemount provider from the Kubernetes Pod
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, brige_request: dict):
        """
        Validate the bridgemount request
        """
        raise NotImplementedError
