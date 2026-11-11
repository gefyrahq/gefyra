from kopf import TemporaryError


class BridgeMountException(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message


class BridgeMountInstallException(BridgeMountException):
    pass


class BridgeMountTargetException(BridgeMountException):
    pass


class BridgeMountRolloutInProgress(TemporaryError):
    """Wait for the target Pods to share a controller before changing the mount."""
