from dataclasses import dataclass


@dataclass
class GefyraLocalContainer:
    """
    A container managed(/started) by Gefyra
    """

    id: str
    short_id: str
    name: str
    address: str
    namespace: str
