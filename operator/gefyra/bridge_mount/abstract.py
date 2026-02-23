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
    def target_exists(self) -> bool:
        """
        Check whether the bridge mount target still exists in the cluster.

        Used by the reconciliation loop to detect removed targets and
        transition the bridge mount to the MISSING state.

        :return: True if the target exists, False if it has been removed.
        :raises: Non-404 API errors are propagated so callers can
                 distinguish "not found" from transient failures.
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, bridge_request: dict, hits: dict | None):
        """
        Validate the bridgemount request
        """
        raise NotImplementedError
