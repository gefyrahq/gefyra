from gefyra.__main__ import up_parser, up_command
from gefyra.configuration import ClientConfiguration, __VERSION__


REGISTRY_URL = "my-reg.io/gefyra"
QUAY_REGISTRY_URL = "quay.io/gefyra"
STOWAWAY_LATEST = "my-reg.io/gefyra/stowaway:latest"
CARGO_LATEST = "my-reg.io/gefyra/cargo:latest"
OPERATOR_LATEST = "my-reg.io/gefyra/operator:latest"
CARRIER_LATEST = "my-reg.io/gefyra/carrier:latest"


def test_parse_registry_a():
    args = up_parser.parse_args(["--registry", REGISTRY_URL])
    configuration = ClientConfiguration(registry_url=args.registry)
    assert configuration.REGISTRY_URL == REGISTRY_URL


def test_parse_registry_b():
    args = up_parser.parse_args(["--registry", "my-reg.io/gefyra/"])
    configuration = ClientConfiguration(registry_url=args.registry)
    assert configuration.REGISTRY_URL, REGISTRY_URL

    args = up_parser.parse_args(["-r", "my-reg.io/gefyra/"])
    configuration = ClientConfiguration(registry_url=args.registry)
    assert configuration.REGISTRY_URL == REGISTRY_URL


def test_parse_no_registry():
    args = up_parser.parse_args()
    configuration = ClientConfiguration(registry_url=args.registry)
    assert configuration.REGISTRY_URL == QUAY_REGISTRY_URL


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
    args = up_parser.parse_args(["--stowaway", STOWAWAY_LATEST])
    configuration = ClientConfiguration(stowaway_image_url=args.stowaway)
    assert configuration.STOWAWAY_IMAGE == STOWAWAY_LATEST

    args = up_parser.parse_args(["-s", STOWAWAY_LATEST])
    configuration = ClientConfiguration(stowaway_image_url=args.stowaway)
    assert configuration.STOWAWAY_IMAGE == STOWAWAY_LATEST

    args = up_parser.parse_args(["-s", STOWAWAY_LATEST, "-r", QUAY_REGISTRY_URL])
    configuration = ClientConfiguration(
        registry_url=args.registry, stowaway_image_url=args.stowaway
    )
    assert configuration.STOWAWAY_IMAGE == STOWAWAY_LATEST


def test_parse_cargo_image():
    args = up_parser.parse_args(["--cargo", CARGO_LATEST])
    configuration = ClientConfiguration(cargo_image_url=args.cargo)
    assert configuration.CARGO_IMAGE == CARGO_LATEST

    args = up_parser.parse_args(["-a", CARGO_LATEST])
    configuration = ClientConfiguration(cargo_image_url=args.cargo)
    assert configuration.CARGO_IMAGE == CARGO_LATEST

    args = up_parser.parse_args(["-a", CARGO_LATEST, "-r", QUAY_REGISTRY_URL])
    configuration = ClientConfiguration(
        registry_url=args.registry, cargo_image_url=args.cargo
    )
    assert configuration.CARGO_IMAGE == CARGO_LATEST


def test_parse_operator_image():
    args = up_parser.parse_args(["--operator", OPERATOR_LATEST])
    configuration = ClientConfiguration(operator_image_url=args.operator)
    assert configuration.OPERATOR_IMAGE == OPERATOR_LATEST

    args = up_parser.parse_args(["-o", OPERATOR_LATEST])
    configuration = ClientConfiguration(operator_image_url=args.operator)
    assert configuration.OPERATOR_IMAGE == OPERATOR_LATEST

    args = up_parser.parse_args(["-o", OPERATOR_LATEST, "-r", QUAY_REGISTRY_URL])
    configuration = ClientConfiguration(
        registry_url=args.registry, operator_image_url=args.operator
    )
    assert configuration.OPERATOR_IMAGE == OPERATOR_LATEST


def test_parse_carrier_image():
    args = up_parser.parse_args(["--carrier", CARRIER_LATEST])
    configuration = ClientConfiguration(carrier_image_url=args.carrier)
    assert configuration.CARRIER_IMAGE == CARRIER_LATEST

    args = up_parser.parse_args(["-c", CARRIER_LATEST])
    configuration = ClientConfiguration(carrier_image_url=args.carrier)
    assert configuration.CARRIER_IMAGE == CARRIER_LATEST

    args = up_parser.parse_args(["-c", CARRIER_LATEST, "-r", QUAY_REGISTRY_URL])
    configuration = ClientConfiguration(
        registry_url=args.registry, carrier_image_url=args.carrier
    )
    assert configuration.CARRIER_IMAGE == CARRIER_LATEST


def test_parse_combination_a():
    args = up_parser.parse_args(["-c", CARRIER_LATEST])
    configuration = ClientConfiguration(
        registry_url=args.registry,
        stowaway_image_url=args.stowaway,
        operator_image_url=args.operator,
        cargo_image_url=args.cargo,
        carrier_image_url=args.carrier,
    )
    assert configuration.REGISTRY_URL == QUAY_REGISTRY_URL
    assert configuration.OPERATOR_IMAGE == f"quay.io/gefyra/operator:{__VERSION__}"
    assert configuration.CARRIER_IMAGE == CARRIER_LATEST


def test_parse_combination_b():
    args = up_parser.parse_args(["-r", REGISTRY_URL])
    configuration = ClientConfiguration(
        registry_url=args.registry,
        stowaway_image_url=args.stowaway,
        operator_image_url=args.operator,
        cargo_image_url=args.cargo,
        carrier_image_url=args.carrier,
    )
    assert configuration.REGISTRY_URL == REGISTRY_URL
    assert configuration.OPERATOR_IMAGE == f"my-reg.io/gefyra/operator:{__VERSION__}"
    assert configuration.CARRIER_IMAGE == f"my-reg.io/gefyra/carrier:{__VERSION__}"


def test_parse_combination_c():
    args = up_parser.parse_args(
        ["-r", REGISTRY_URL, "-c", "quay.io/gefyra/carrier:latest"]
    )
    configuration = ClientConfiguration(
        registry_url=args.registry,
        stowaway_image_url=args.stowaway,
        operator_image_url=args.operator,
        cargo_image_url=args.cargo,
        carrier_image_url=args.carrier,
    )
    assert configuration.REGISTRY_URL == REGISTRY_URL
    assert configuration.OPERATOR_IMAGE == f"my-reg.io/gefyra/operator:{__VERSION__}"
    assert configuration.CARRIER_IMAGE == "quay.io/gefyra/carrier:latest"


def test_parse_endpoint():
    args = up_parser.parse_args(["-e", "10.30.34.25:31820"])
    configuration = ClientConfiguration(
        cargo_endpoint=args.endpoint,
        registry_url=args.registry,
        stowaway_image_url=args.stowaway,
        operator_image_url=args.operator,
        cargo_image_url=args.cargo,
        carrier_image_url=args.carrier,
    )
    assert configuration.CARGO_ENDPOINT == "10.30.34.25:31820"


def test_parse_up_fct(monkeypatch):
    monkeypatch.setattr("gefyra.api.up", lambda config: True)
    args = up_parser.parse_args(["-e", "10.30.34.25:31820"])
    up_command(args)
