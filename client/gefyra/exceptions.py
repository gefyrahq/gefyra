class GefyraClientAlreadyExists(RuntimeError):
    pass


class GefyraClientNotFound(RuntimeError):
    pass


class ClientConfigurationError(RuntimeError):
    pass


class MinikubeError(RuntimeError):
    pass


class GefyraBridgeError(RuntimeError):
    pass


class CommandTimeoutError(RuntimeError):
    pass


class GefyraConnectionError(RuntimeError):
    pass


class ClusterError(RuntimeError):
    pass


class PodNotFoundError(RuntimeError):
    pass


class WorkloadNotFoundError(RuntimeError):
    pass
