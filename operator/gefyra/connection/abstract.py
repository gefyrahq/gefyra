from abc import ABC, abstractmethod
from typing import List, Optional


class AbstractGefyraConnectionProvider(ABC):
    provider_type = ""

    @abstractmethod
    async def install(self, config: dict = {}) -> bool:
        """
        Install this Gefyra connection provider to the cluster
        """
        raise NotImplementedError

    @abstractmethod
    async def uninstall(self, config: dict = {}) -> bool:
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
    async def add_peer(self, peer_id: str):
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
