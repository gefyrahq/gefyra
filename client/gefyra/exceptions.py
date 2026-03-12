class GefyraClientAlreadyExists(RuntimeError):
    pass


class ClientConfigurationError(RuntimeError):
    pass


class MinikubeError(RuntimeError):
    pass


class GefyraBridgeError(RuntimeError):
    pass


class CommandTimeoutError(TimeoutError):
    exit_code = 100


class GefyraObjectNotFound(RuntimeError):
    exit_code = 101


class GefyraClientNotFound(GefyraObjectNotFound):
    pass


class GefyraCargoNotFound(GefyraObjectNotFound):
    pass


class GefyraBridgeNotFound(GefyraObjectNotFound):
    pass


class GefyraBridgeMountNotFound(GefyraObjectNotFound):
    pass


class GefyraConnectionError(RuntimeError):
    pass


class ClusterError(RuntimeError):
    pass


class PodNotFoundError(RuntimeError):
    pass


class WorkloadNotFoundError(RuntimeError):
    pass
