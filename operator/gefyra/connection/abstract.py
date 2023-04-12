from abc import ABC, abstractmethod
from typing import List, Optional


class AbstractGefyraConnectionProvider(ABC):
    provider_type = ""

    @abstractmethod
    async def installed(self, config: dict = {}) -> bool:
        """
        Check if this Gefyra connection provider is properly installed to the cluster
        """
        raise NotImplementedError

    @abstractmethod
    async def install(self, config: dict = {}):
        """
        Install this Gefyra connection provider to the cluster
        """
        raise NotImplementedError

    @abstractmethod
    async def uninstall(self, config: dict = {}):
        """
        Uninstall this Gefyra connection provider from the cluster
        """
        raise NotImplementedError

    @abstractmethod
    async def ready(self) -> bool:
        """
        Returns True if the connection provider is ready to accept peer connections
        """
        raise NotImplementedError

    @abstractmethod
    async def add_peer(self, peer_id: str, parameters: dict = {}):
        """
        Add a new peer to the connection provider
        """
        raise NotImplementedError

    @abstractmethod
    async def remove_peer(self, peer_id: str):
        """
        Remove a peer from the connection provider
        """
        raise NotImplementedError

    @abstractmethod
    async def get_peer_config(self, peer_id: str) -> dict[str, str]:
        """
        Returns a dict of configuration values for the peer to be stored in the Peer CRD
        """
        raise NotImplementedError

    @abstractmethod
    async def peer_exists(self, peer_id: str) -> bool:
        """
        Returns True if the peer exists, otherwise False
        """
        raise NotImplementedError

    @abstractmethod
    async def add_destination(
        self, peer_id: str, destination_ip: str, destination_port: int
    ):
        """
        Add a destintation route to this connection provider proxy
        """
        raise NotImplementedError

    @abstractmethod
    async def remove_destination(
        self, peer_id: str, destination_ip: str, destination_port: int
    ):
        """
        Remove a destintation route from this connection provider proxy
        """
        raise NotImplementedError
