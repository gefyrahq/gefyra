from decouple import config


class OperatorConfiguration:
    def __init__(self):
        self.NAMESPACE = config("GEFYRA_NAMESPACE", default="gefyra")
        self.STOWAWAY_IMAGE = config(
            "GEFYRA_STOWAWAY_IMAGE", default="quay.io/gefyra/stowaway"
        )
        self.STOWAWAY_IMAGE_PULLPOLICY = config(
            "GEFYRA_STOWAWAY_IMAGE_PULLPOLICY", default="IfNotPresent"
        )
        self.STOWAWAY_TAG = config("GEFYRA_STOWAWAY_TAG", default="latest")
        self.WIREGUARD_EXT_PORT = config(
            "GEFYRA_STOWAWAY_SERVERPORT", cast=int, default=31820
        )
        self.WIREGUARD_EXT_PORT_TCP = config(
            "GEFYRA_STOWAWAY_SERVERPORT_TCP", cast=int, default=31821
        )
        self.STOWAWAY_PGID = config("GEFYRA_STOWAWAY_PGID", default="1000")
        self.STOWAWAY_PUID = config("GEFYRA_STOWAWAY_PUID", default="1000")
        self.CONNECTION_PROVIDER_STARTUP_TIMEOUT = config(
            "CONNECTION_PROVIDER_STARTUP_TIMEOUT", cast=int, default=180
        )
        self.STOWAWAY_PEER_DNS = config("GEFYRA_STOWAWAY_PUID", default="auto")
        self.STOWAWAY_PEER_CONFIG_PATH = config(
            "GEFYRA_STOWAWAY_PEER_CONFIG_PATH", default="/config/"
        )
        self.STOWAWAY_INTERNAL_SUBNET = config(
            "GEFYRA_INTERNAL_SUBNET", default="192.168.99.0"
        )

        self.STOWAWAY_PROXYROUTE_CONFIGMAPNAME = "gefyra-stowaway-proxyroutes"
        self.STOWAWAY_CONFIGMAPNAME = "gefyra-stowaway-config"
        # Carrier
        self.CARRIER_IMAGE = config(
            "GEFYRA_CARRIER_IMAGE", default="quay.io/gefyra/carrier"
        )
        self.CARRIER_IMAGE_TAG = config("GEFYRA_CARRIER_IMAGE_TAG", default="latest")
        self.CARRIER_STARTUP_TIMEOUT = config(
            "GEFYRA_CARRIER_STARTUP_TIMEOUT", cast=int, default=60
        )

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k.isupper()}

    def __str__(self):
        return str(self.to_dict())


configuration = OperatorConfiguration()
