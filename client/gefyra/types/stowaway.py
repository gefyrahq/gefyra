from dataclasses import dataclass


@dataclass
class StowawayParameter:
    # the subnet for a client
    subnet: str


@dataclass
class StowawayConfig:
    # the wireguard connection data
    # Interface.Address: 192.168.99.2
    iaddress: str
    # Interface.DNS: 192.168.99.1
    idns: str
    # Interface.ListenPort: 51820
    iport: int
    # Interface.PrivateKey: MFQ3v+...=
    iprivatekey: str
    # Peer.AllowedIPs: 0.0.0.0/0, ::/0
    pallowedips: str
    # Peer.Endpoint: 95.91.248.4:31820
    pendpoint: str
    # Peer.PublicKey: sy8jXi7...=
    ppublickey: str
    # Peer.PresharedKey: WCWY20...=
    presharedkey: str
