from dataclasses import dataclass, field
from typing import Dict

from gefyra.configuration import __VERSION__


@dataclass
class GefyraInstallOptions:
    namespace: str = field(
        default_factory=lambda: "gefyra",
        metadata=dict(
            help="The namespace to install Gefyra into (default: gefyra)", short="ns"
        ),
    )
    version: str = field(
        default_factory=lambda: __VERSION__,
        metadata=dict(
            help=(
                "Set the Operator version; components are created according to this"
                f" Gefyra version (default: {__VERSION__})"
            )
        ),
    )
    service_type: str = field(
        default_factory=lambda: "NodePort",
        metadata=dict(
            help=(
                "The Kubernetes service for Stowaway to expose the Wireguard endpoint"
                " (default: NodePort)"
            )
        ),
    )
    service_port: int = field(
        default_factory=lambda: 31820,
        metadata=dict(
            help=(
                "The port for Stowaway to expose the Wireguard endpoint (default:"
                " 31820)"
            )
        ),
    )
    service_labels: Dict[str, str] = field(
        default_factory=lambda: {},
        metadata=dict(
            help="Additional Kubernetes labels for the Stowaway service (default: [])",
            type="array",
        ),
    )
    service_annotations: Dict[str, str] = field(
        default_factory=lambda: {},
        metadata=dict(
            help="Kubernetes annotations for the Stowaway service (default: [])",
            type="array",
        ),
    )
    registry: str = field(
        default_factory=lambda: "quay.io/gefyra",
        metadata=dict(
            help="The registry URL for the images (default: quay.io/gefyra)",
        ),
    )
    mtu: int = field(
        default_factory=lambda: 1340,
        metadata=dict(
            help="The MTU for the Wireguard interface (default: 1340)",
        ),
    )
    stowaway_storage: int = field(
        default_factory=lambda: 64,
        metadata=dict(
            help="The storage size for the Stowaway PVC in Mi (default: 64)",
        ),
    )
    max_client_connection_age: int | None = field(
        default_factory=lambda: None,
        metadata=dict(
            help=(
                "The maximum age of a Stowaway connection in seconds (default: None)"
            ),
        ),
    )
    disable_client_sa_management: bool = field(
        default=False,
        metadata=dict(
            help="Whether to create/manage client service accounts for Gefyra (default: False)",
            type=bool,
            is_flag=True,
        ),
    )
