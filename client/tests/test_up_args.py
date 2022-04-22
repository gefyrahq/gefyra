from gefyra.__main__ import up_parser, up_command
from gefyra.configuration import ClientConfiguration, __VERSION__


def test_parse_registry_a():
    args = up_parser.parse_args(["--registry", "my-reg.io/gefyra"])
    configuration = ClientConfiguration(registry_url=args.registry)
    assert configuration.REGISTRY_URL == "my-reg.io/gefyra"


def test_parse_registry_b():
    args = up_parser.parse_args(["--registry", "my-reg.io/gefyra/"])
    configuration = ClientConfiguration(registry_url=args.registry)
    assert configuration.REGISTRY_URL, "my-reg.io/gefyra"

    args = up_parser.parse_args(["-r", "my-reg.io/gefyra/"])
    configuration = ClientConfiguration(registry_url=args.registry)
    assert configuration.REGISTRY_URL == "my-reg.io/gefyra"


def test_parse_no_registry():
    args = up_parser.parse_args()
    configuration = ClientConfiguration(registry_url=args.registry)
    assert configuration.REGISTRY_URL == "quay.io/gefyra"


def test_parse_no_stowaway_image():
    args = up_parser.parse_args()
    configuration = ClientConfiguration(stowaway_image_url=args.stowaway)
    assert configuration.STOWAWAY_IMAGE == f"quay.io/gefyra/stowaway:{__VERSION__}"


def test_parse_no_carrier_image():
    args = up_parser.parse_args()
    configuration = ClientConfiguration(carrier_image_url=args.carrier)
    assert configuration.CARRIER_IMAGE == f"quay.io/gefyra/carrier:{__VERSION__}"


def test_parse_no_operator_image():
    args = up_parser.parse_args()
    configuration = ClientConfiguration(operator_image_url=args.operator)
    assert configuration.OPERATOR_IMAGE == f"quay.io/gefyra/operator:{__VERSION__}"


def test_parse_no_cargo_image():
    args = up_parser.parse_args()
    configuration = ClientConfiguration(cargo_image_url=args.cargo)
    assert configuration.CARGO_IMAGE == f"quay.io/gefyra/cargo:{__VERSION__}"


def test_parse_stowaway_image():
    args = up_parser.parse_args(["--stowaway", "my-reg.io/gefyra/stowaway:latest"])
    configuration = ClientConfiguration(stowaway_image_url=args.stowaway)
    assert configuration.STOWAWAY_IMAGE == "my-reg.io/gefyra/stowaway:latest"

    args = up_parser.parse_args(["-s", "my-reg.io/gefyra/stowaway:latest"])
    configuration = ClientConfiguration(stowaway_image_url=args.stowaway)
    assert configuration.STOWAWAY_IMAGE == "my-reg.io/gefyra/stowaway:latest"

    args = up_parser.parse_args(
        ["-s", "my-reg.io/gefyra/stowaway:latest", "-r", "quay.io/gefyra"]
    )
    configuration = ClientConfiguration(
        registry_url=args.registry, stowaway_image_url=args.stowaway
    )
    assert configuration.STOWAWAY_IMAGE == "my-reg.io/gefyra/stowaway:latest"


def test_parse_cargo_image():
    args = up_parser.parse_args(["--cargo", "my-reg.io/gefyra/cargo:latest"])
    configuration = ClientConfiguration(cargo_image_url=args.cargo)
    assert configuration.CARGO_IMAGE == "my-reg.io/gefyra/cargo:latest"

    args = up_parser.parse_args(["-a", "my-reg.io/gefyra/cargo:latest"])
    configuration = ClientConfiguration(cargo_image_url=args.cargo)
    assert configuration.CARGO_IMAGE == "my-reg.io/gefyra/cargo:latest"

    args = up_parser.parse_args(
        ["-a", "my-reg.io/gefyra/cargo:latest", "-r", "quay.io/gefyra"]
    )
    configuration = ClientConfiguration(
        registry_url=args.registry, cargo_image_url=args.cargo
    )
    assert configuration.CARGO_IMAGE == "my-reg.io/gefyra/cargo:latest"


def test_parse_operator_image():
    args = up_parser.parse_args(["--operator", "my-reg.io/gefyra/operator:latest"])
    configuration = ClientConfiguration(operator_image_url=args.operator)
    assert configuration.OPERATOR_IMAGE == "my-reg.io/gefyra/operator:latest"

    args = up_parser.parse_args(["-o", "my-reg.io/gefyra/operator:latest"])
    configuration = ClientConfiguration(operator_image_url=args.operator)
    assert configuration.OPERATOR_IMAGE == "my-reg.io/gefyra/operator:latest"

    args = up_parser.parse_args(
        ["-o", "my-reg.io/gefyra/operator:latest", "-r", "quay.io/gefyra"]
    )
    configuration = ClientConfiguration(
        registry_url=args.registry, operator_image_url=args.operator
    )
    assert configuration.OPERATOR_IMAGE == "my-reg.io/gefyra/operator:latest"


def test_parse_carrier_image():
    args = up_parser.parse_args(["--carrier", "my-reg.io/gefyra/carrier:latest"])
    configuration = ClientConfiguration(carrier_image_url=args.carrier)
    assert configuration.CARRIER_IMAGE == "my-reg.io/gefyra/carrier:latest"

    args = up_parser.parse_args(["-c", "my-reg.io/gefyra/carrier:latest"])
    configuration = ClientConfiguration(carrier_image_url=args.carrier)
    assert configuration.CARRIER_IMAGE == "my-reg.io/gefyra/carrier:latest"

    args = up_parser.parse_args(
        ["-c", "my-reg.io/gefyra/carrier:latest", "-r", "quay.io/gefyra"]
    )
    configuration = ClientConfiguration(
        registry_url=args.registry, carrier_image_url=args.carrier
    )
    assert configuration.CARRIER_IMAGE == "my-reg.io/gefyra/carrier:latest"


def test_parse_combination_a():
    args = up_parser.parse_args(["-c", "my-reg.io/gefyra/carrier:latest"])
    configuration = ClientConfiguration(
        registry_url=args.registry,
        stowaway_image_url=args.stowaway,
        operator_image_url=args.operator,
        cargo_image_url=args.cargo,
        carrier_image_url=args.carrier,
    )
    assert configuration.REGISTRY_URL == "quay.io/gefyra"
    assert configuration.OPERATOR_IMAGE == f"quay.io/gefyra/operator:{__VERSION__}"
    assert configuration.CARRIER_IMAGE == "my-reg.io/gefyra/carrier:latest"


def test_parse_combination_b():
    args = up_parser.parse_args(["-r", "my-reg.io/gefyra"])
    configuration = ClientConfiguration(
        registry_url=args.registry,
        stowaway_image_url=args.stowaway,
        operator_image_url=args.operator,
        cargo_image_url=args.cargo,
        carrier_image_url=args.carrier,
    )
    assert configuration.REGISTRY_URL == "my-reg.io/gefyra"
    assert configuration.OPERATOR_IMAGE == f"my-reg.io/gefyra/operator:{__VERSION__}"
    assert configuration.CARRIER_IMAGE == f"my-reg.io/gefyra/carrier:{__VERSION__}"


def test_parse_combination_c():
    args = up_parser.parse_args(
        ["-r", "my-reg.io/gefyra", "-c", "quay.io/gefyra/carrier:latest"]
    )
    configuration = ClientConfiguration(
        registry_url=args.registry,
        stowaway_image_url=args.stowaway,
        operator_image_url=args.operator,
        cargo_image_url=args.cargo,
        carrier_image_url=args.carrier,
    )
    assert configuration.REGISTRY_URL == "my-reg.io/gefyra"
    assert configuration.OPERATOR_IMAGE == f"my-reg.io/gefyra/operator:{__VERSION__}"
    assert configuration.CARRIER_IMAGE == "quay.io/gefyra/carrier:latest"


def test_parse_endpoint():
    args = up_parser.parse_args(["-e", "10.30.34.25"])
    configuration = ClientConfiguration(
        cargo_endpoint=args.endpoint,
        registry_url=args.registry,
        stowaway_image_url=args.stowaway,
        operator_image_url=args.operator,
        cargo_image_url=args.cargo,
        carrier_image_url=args.carrier,
    )
    assert configuration.CARGO_ENDPOINT == "10.30.34.25"


def test_parse_up_fct(monkeypatch):
    monkeypatch.setattr("gefyra.api.up", lambda config: True)
    args = up_parser.parse_args(["-e", "10.30.34.25"])
    up_command(args)
