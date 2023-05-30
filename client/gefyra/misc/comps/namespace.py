# flake8: noqa
from gefyra.types import GefyraInstallOptions


def data(params: GefyraInstallOptions) -> list[dict]:
    return [
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": params.namespace},
        }
    ]
