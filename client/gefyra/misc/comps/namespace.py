# flake8: noqa
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gefyra.types import GefyraInstallOptions


def data(params: "GefyraInstallOptions") -> list[dict]:
    return [
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": params.namespace},
        }
    ]
