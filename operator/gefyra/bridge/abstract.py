from abc import ABC, abstractmethod
from typing import List


class AbstractGefyraBridgeProvider(ABC):
    """The Gefyra bridge provider gets created for each (target Pod plus target container) combination"""

    provider_type = ""

    @abstractmethod
    def install(self, parameters: dict = {}):
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
    def uninstall(self) -> bool:
        """
        Uninstall this Gefyra bridge provider from the Kubernetes Pod
        """
        raise NotImplementedError

    @abstractmethod
    def add_destination(self, destination: str, parameters: dict = {}):
        """
        Add a new destination to the bridge provider

        :param destination: the destination to be added in the form of IP:PORT
        """
        raise NotImplementedError

    @abstractmethod
    def remove_destination(self, destination: str):
        """
        Remove a bridge from the bridge provider

        :param destination: the destination to be removed in the form of IP:PORT
        """
        raise NotImplementedError

    @abstractmethod
    def destination_exists(self, destination: str) -> bool:
        """
        Returns True if the bridge exists, otherwise False
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, brige_request: dict):
        """
        Validate the bridge request
        """
        raise NotImplementedError
