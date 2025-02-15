from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AbstractGefyraShadowProvider(ABC):
    """The Gefyra shadow provider"""

    provider_type = ""

    @abstractmethod
    def install(self, parameters: Optional[Dict[Any, Any]] = None):
        """
        Install this Gefyra shadow provider to the Kubernetes Pod
        """
        raise NotImplementedError

    @abstractmethod
    def installed(self) -> bool:
        """
        Check if this Gefyra shadow provider is properly installed
        """
        raise NotImplementedError

    @abstractmethod
    def ready(self) -> bool:
        """
        Check if this Gefyra shadow provider is ready for shadows
        """
        raise NotImplementedError

    @abstractmethod
    def uninstall(self):
        """
        Uninstall this Gefyra shadow provider from the Kubernetes Pod
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, brige_request: dict):
        """
        Validate the shadow request
        """
        raise NotImplementedError
