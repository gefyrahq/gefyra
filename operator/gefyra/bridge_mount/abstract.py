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
        Check whether the target workload and its Kubernetes namespace
        still exist in the cluster.

        Used by the reconciliation loop to detect removed targets and
        transition the bridge mount to the MISSING state.

        :return: True if both the namespace and workload exist, False if
                 either has been deleted (API returns 404).
        :raises: Non-404 API errors (e.g. ``ApiException`` for 403/500,
                 or ``RuntimeError`` from workload lookup) are propagated
                 so callers can distinguish "not found" from transient
                 infrastructure or RBAC failures.
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, bridge_request: dict, hits: dict | None):
        """
        Validate the bridgemount request
        """
        raise NotImplementedError
