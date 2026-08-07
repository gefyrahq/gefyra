from collections.abc import Callable

from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount
from gefyra.configuration import OperatorConfiguration


class Carrier2BridgeMountBuilder:
    def __init__(self):
        self._instances = {}

    def __call__(
        self,
        configuration: OperatorConfiguration,
        name: str,
        target_namespace: str,
        target: str,
        target_container: str,
        post_event_function: Callable,
        parameter: dict,
        logger,
        **_ignored,
    ):
        instance = Carrier2BridgeMount(
            configuration=configuration,
            target_namespace=target_namespace,
            target=target,
            target_container=target_container,
            name=name,
            post_event_function=post_event_function,
            logger=logger,
            parameter=parameter,
        )
        return instance
