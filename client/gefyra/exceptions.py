class GefyraClientAlreadyExists(RuntimeError):
    pass


class GefyraClientNotFound(RuntimeError):
    pass


class ClientConfigurationError(RuntimeError):
    pass


class ClusterError(RuntimeError):
    pass


class PodNotFoundError(RuntimeError):
    pass
