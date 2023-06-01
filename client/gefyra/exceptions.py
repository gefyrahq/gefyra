class GefyraException(RuntimeError):
    def __init__(self, message, error_code, hint=None):
        super().__init__(message)
        self.error_code = error_code
        self.hint = hint


class CargoNotFound(GefyraException):
    def __init__(self):
        super().__init__(
            "Gefyra Cargo not running.", 200, "Please run 'gefyra up' first."
        )


class ImproperlyConfiguredCargo(GefyraException):
    def __init__(self):
        super().__init__(
            "Gefyra Cargo is not properly configured.",
            201,
            "Please set up Gefyra again with 'gefyra down' and 'gefyra up'.",
        )
