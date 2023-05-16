from abc import ABC, abstractmethod
from types import MappingProxyType


class AbstractGefyraBridgeProvider(ABC):
    """The Gefyra bridge provider gets created for each (target Pod plus
    target container) combination"""

    provider_type = ""

    @abstractmethod
    def install(self, parameters: dict = MappingProxyType({})):
        """
        Install this Gefyra bridge provider to the Kubernetes Pod
        """
        raise NotImplementedError

    @abstractmethod
    def installed(self) -> bool:
        """
        Check if this Gefyra bridge provider is properly installed
        """
        raise NotImplementedError

    @abstractmethod
    def ready(self) -> bool:
        """
        Check if this Gefyra bridge provider is ready for bridges
        """
        raise NotImplementedError

    @abstractmethod
    def uninstall(self):
        """
        Uninstall this Gefyra bridge provider from the Kubernetes Pod
        """
        raise NotImplementedError

    @abstractmethod
    def add_proxy_route(
        self,
        container_port: int,
        destination_host: str,
        destination_port: int,
        parameters: dict = MappingProxyType({}),
    ):
        """
        Add a new proxy_route to the bridge provider
        """
        raise NotImplementedError

    @abstractmethod
    def remove_proxy_route(
        self, container_port: int, destination_host: str, destination_port: int
    ):
        """
        Remove a bridge from the bridge provider

        :param proxy_route: the proxy_route to be removed in the form of IP:PORT
        """
        raise NotImplementedError

    @abstractmethod
    def proxy_route_exists(
        self, container_port: int, destination_host: str, destination_port: int
    ) -> bool:
        """
        Returns True if a proxy route exists for this port, otherwise False
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, brige_request: dict):
        """
        Validate the bridge request
        """
        raise NotImplementedError
