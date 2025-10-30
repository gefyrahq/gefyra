from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AbstractGefyraBridgeProvider(ABC):

    @abstractmethod
    def install(self, parameters: Optional[Dict[Any, Any]] = None):
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
        parameters: Optional[Dict[Any, Any]] = None,
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
    def validate(self, bridge_request: dict, hints: dict | None):
        """
        Validate the bridge request
        """
        raise NotImplementedError
