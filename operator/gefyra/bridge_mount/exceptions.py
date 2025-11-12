class BridgeMountException(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message


class BridgeMountInstallException(BridgeMountException):
    pass


class BridgeMountTargetException(BridgeMountException):
    pass
