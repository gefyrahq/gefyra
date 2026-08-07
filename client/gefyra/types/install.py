from dataclasses import dataclass, field

from gefyra.configuration import __VERSION__


@dataclass
class GefyraInstallOptions:
    namespace: str = field(
        default_factory=lambda: "gefyra",
        metadata={
            "help": "The namespace to install Gefyra into (default: gefyra)",
            "short": "ns",
        },
    )
    version: str = field(
        default_factory=lambda: __VERSION__,
        metadata={
            "help": (
                "Set the Operator version; components are created according to this"
                f" Gefyra version (default: {__VERSION__})"
            )
        },
    )
    service_type: str = field(
        default_factory=lambda: "NodePort",
        metadata={
            "help": (
                "The Kubernetes service for Stowaway to expose the Wireguard endpoint"
                " (default: NodePort)"
            )
        },
    )
    service_port: int = field(
        default_factory=lambda: 31820,
        metadata={
            "help": (
                "The port for Stowaway to expose the Wireguard endpoint (default:"
                " 31820)"
            )
        },
    )
    service_labels: dict[str, str] = field(
        default_factory=dict,
        metadata={
            "help": "Additional Kubernetes labels for the Stowaway service (default: [])",
            "type": "array",
        },
    )
    service_annotations: dict[str, str] = field(
        default_factory=dict,
        metadata={
            "help": "Kubernetes annotations for the Stowaway service (default: [])",
            "type": "array",
        },
    )
    registry: str = field(
        default_factory=lambda: "quay.io/gefyra",
        metadata={
            "help": "The registry URL for the images (default: quay.io/gefyra)",
        },
    )
    mtu: int | None = field(
        default_factory=lambda: None,
        metadata={
            "help": "The MTU for the Wireguard interface (default: auto-detected by WireGuard)",
        },
    )
    stowaway_storage: int = field(
        default_factory=lambda: 64,
        metadata={
            "help": "The storage size for the Stowaway PVC in Mi (default: 64)",
        },
    )
    max_client_connection_age: int | None = field(
        default_factory=lambda: None,
        metadata={
            "help": (
                "The maximum age of a Stowaway connection in seconds (default: None)"
            ),
        },
    )
    disable_client_sa_management: bool = field(
        default=False,
        metadata={
            "help": "Whether to create/manage client service accounts for Gefyra (default: False)",
            "type": bool,
            "is_flag": True,
        },
    )
    bridge_debug: bool = field(
        default=False,
        metadata={
            "help": "Enable debug logging for GefyraBridgeMounts/GefyraBridges (default: False)",
            "type": bool,
            "is_flag": True,
        },
    )
