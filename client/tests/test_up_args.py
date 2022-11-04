import pytest
from gefyra.__main__ import parser, get_client_configuration
from gefyra.configuration import ClientConfiguration, __VERSION__


REGISTRY_URL = "my-reg.io/gefyra"
QUAY_REGISTRY_URL = "quay.io/gefyra"
STOWAWAY_LATEST = "my-reg.io/gefyra/stowaway:latest"
CARGO_LATEST = "my-reg.io/gefyra/cargo:latest"
OPERATOR_LATEST = "my-reg.io/gefyra/operator:latest"
CARRIER_LATEST = "my-reg.io/gefyra/carrier:latest"
KUBE_CONFIG = "~/.kube/config"


def test_parse_registry_a():
    args = parser.parse_args(["up", "--registry", REGISTRY_URL])
    configuration = ClientConfiguration(registry_url=args.registry_url)
    assert configuration.REGISTRY_URL == REGISTRY_URL


def test_parse_registry_b():
    args = parser.parse_args(["up", "--registry", "my-reg.io/gefyra/"])
    configuration = ClientConfiguration(registry_url=args.registry_url)
    assert configuration.REGISTRY_URL, REGISTRY_URL

    args = parser.parse_args(["up", "-r", "my-reg.io/gefyra/"])
    configuration = ClientConfiguration(registry_url=args.registry_url)
    assert configuration.REGISTRY_URL == REGISTRY_URL


def test_parse_no_registry():
    args = parser.parse_args(["up"])
    configuration = ClientConfiguration(registry_url=args.registry_url)
    assert configuration.REGISTRY_URL == QUAY_REGISTRY_URL


def test_parse_no_stowaway_image():
    args = parser.parse_args(["up"])
    configuration = ClientConfiguration(stowaway_image_url=args.stowaway_image_url)
    assert configuration.STOWAWAY_IMAGE == f"quay.io/gefyra/stowaway:{__VERSION__}"


def test_parse_no_carrier_image():
    args = parser.parse_args(["up"])
    configuration = ClientConfiguration(carrier_image_url=args.carrier_image_url)
    assert configuration.CARRIER_IMAGE == f"quay.io/gefyra/carrier:{__VERSION__}"


def test_parse_no_operator_image():
    args = parser.parse_args(["up"])
    configuration = ClientConfiguration(operator_image_url=args.operator_image_url)
    assert configuration.OPERATOR_IMAGE == f"quay.io/gefyra/operator:{__VERSION__}"


def test_parse_no_cargo_image():
    args = parser.parse_args(["up"])
    configuration = ClientConfiguration(cargo_image_url=args.cargo_image_url)
    assert configuration.CARGO_IMAGE == f"quay.io/gefyra/cargo:{__VERSION__}"


def test_parse_stowaway_image():
    args = parser.parse_args(["up", "--stowaway", STOWAWAY_LATEST])
    configuration = ClientConfiguration(stowaway_image_url=args.stowaway_image_url)
    assert configuration.STOWAWAY_IMAGE == STOWAWAY_LATEST

    args = parser.parse_args(["up", "-s", STOWAWAY_LATEST])
    configuration = ClientConfiguration(stowaway_image_url=args.stowaway_image_url)
    assert configuration.STOWAWAY_IMAGE == STOWAWAY_LATEST

    args = parser.parse_args(["up", "-s", STOWAWAY_LATEST, "-r", QUAY_REGISTRY_URL])
    configuration = ClientConfiguration(
        registry_url=args.registry_url, stowaway_image_url=args.stowaway_image_url
    )
    assert configuration.STOWAWAY_IMAGE == STOWAWAY_LATEST


def test_parse_cargo_image():
    args = parser.parse_args(["up", "--cargo", CARGO_LATEST])
    configuration = ClientConfiguration(cargo_image_url=args.cargo_image_url)
    assert configuration.CARGO_IMAGE == CARGO_LATEST

    args = parser.parse_args(["up", "-a", CARGO_LATEST])
    configuration = ClientConfiguration(cargo_image_url=args.cargo_image_url)
    assert configuration.CARGO_IMAGE == CARGO_LATEST

    args = parser.parse_args(["up", "-a", CARGO_LATEST, "-r", QUAY_REGISTRY_URL])
    configuration = ClientConfiguration(
        registry_url=args.registry_url, cargo_image_url=args.cargo_image_url
    )
    assert configuration.CARGO_IMAGE == CARGO_LATEST


def test_parse_operator_image():
    args = parser.parse_args(["up", "--operator", OPERATOR_LATEST])
    configuration = ClientConfiguration(operator_image_url=args.operator_image_url)
    assert configuration.OPERATOR_IMAGE == OPERATOR_LATEST

    args = parser.parse_args(["up", "-o", OPERATOR_LATEST])
    configuration = ClientConfiguration(operator_image_url=args.operator_image_url)
    assert configuration.OPERATOR_IMAGE == OPERATOR_LATEST

    args = parser.parse_args(["up", "-o", OPERATOR_LATEST, "-r", QUAY_REGISTRY_URL])
    configuration = ClientConfiguration(
        registry_url=args.registry_url, operator_image_url=args.operator_image_url
    )
    assert configuration.OPERATOR_IMAGE == OPERATOR_LATEST


def test_parse_carrier_image():
    args = parser.parse_args(["up", "--carrier", CARRIER_LATEST])
    configuration = ClientConfiguration(carrier_image_url=args.carrier_image_url)
    assert configuration.CARRIER_IMAGE == CARRIER_LATEST

    args = parser.parse_args(["up", "-c", CARRIER_LATEST])
    configuration = ClientConfiguration(carrier_image_url=args.carrier_image_url)
    assert configuration.CARRIER_IMAGE == CARRIER_LATEST

    args = parser.parse_args(["up", "-c", CARRIER_LATEST, "-r", QUAY_REGISTRY_URL])
    configuration = ClientConfiguration(
        registry_url=args.registry_url, carrier_image_url=args.carrier_image_url
    )
    assert configuration.CARRIER_IMAGE == CARRIER_LATEST


def test_parse_combination_a():
    args = parser.parse_args(["up", "-c", CARRIER_LATEST])
    configuration = ClientConfiguration(
        registry_url=args.registry_url,
        stowaway_image_url=args.stowaway_image_url,
        operator_image_url=args.operator_image_url,
        cargo_image_url=args.cargo_image_url,
        carrier_image_url=args.carrier_image_url,
    )
    assert configuration.REGISTRY_URL == QUAY_REGISTRY_URL
    assert configuration.OPERATOR_IMAGE == f"quay.io/gefyra/operator:{__VERSION__}"
    assert configuration.CARRIER_IMAGE == CARRIER_LATEST


def test_parse_combination_b():
    args = parser.parse_args(["up", "-r", REGISTRY_URL])
    configuration = ClientConfiguration(
        registry_url=args.registry_url,
        stowaway_image_url=args.stowaway_image_url,
        operator_image_url=args.operator_image_url,
        cargo_image_url=args.cargo_image_url,
        carrier_image_url=args.carrier_image_url,
    )
    assert configuration.REGISTRY_URL == REGISTRY_URL
    assert configuration.OPERATOR_IMAGE == f"my-reg.io/gefyra/operator:{__VERSION__}"
    assert configuration.CARRIER_IMAGE == f"my-reg.io/gefyra/carrier:{__VERSION__}"


def test_parse_combination_c():
    args = parser.parse_args(
        ["up", "-r", REGISTRY_URL, "-c", "quay.io/gefyra/carrier:latest"]
    )
    configuration = ClientConfiguration(
        registry_url=args.registry_url,
        stowaway_image_url=args.stowaway_image_url,
        operator_image_url=args.operator_image_url,
        cargo_image_url=args.cargo_image_url,
        carrier_image_url=args.carrier_image_url,
    )
    assert configuration.REGISTRY_URL == REGISTRY_URL
    assert configuration.OPERATOR_IMAGE == f"my-reg.io/gefyra/operator:{__VERSION__}"
    assert configuration.CARRIER_IMAGE == "quay.io/gefyra/carrier:latest"


def test_parse_endpoint():
    args = parser.parse_args(["up", "--host", "10.30.34.25"])
    configuration = ClientConfiguration(**get_client_configuration(args))
    assert configuration.CARGO_ENDPOINT == "10.30.34.25:31820"


def test_parse_up_fct(monkeypatch):
    monkeypatch.setattr("gefyra.api.up", lambda config: True)
    args = parser.parse_args(["up", "--host", "10.30.34.25", "--port", "31820"])
    get_client_configuration(args)


def test_parse_up_endpoint_and_minikube(monkeypatch):
    monkeypatch.setattr("gefyra.api.up", lambda config: True)
    args = parser.parse_args(["up", "--host", "10.30.34.25", "--minikube"])
    with pytest.raises(RuntimeError):
        get_client_configuration(args)


def test_parse_up_minikube_not_started(monkeypatch):
    monkeypatch.setattr("gefyra.api.up", lambda config: True)
    args = parser.parse_args(["up", "--minikube"])
    with pytest.raises(RuntimeError):
        get_client_configuration(args)


def test_parse_up_kube_conf():
    configuration = ClientConfiguration(kube_config_file=KUBE_CONFIG)
    assert configuration.KUBE_CONFIG_FILE == KUBE_CONFIG


def test_parse_up_no_kube_conf():
    configuration = ClientConfiguration()
    from kubernetes.config.kube_config import KUBE_CONFIG_DEFAULT_LOCATION

    assert configuration.KUBE_CONFIG_FILE == KUBE_CONFIG_DEFAULT_LOCATION
