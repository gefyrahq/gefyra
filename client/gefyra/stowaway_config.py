"""Stowaway input validation shared by the independently packaged client/operator.

Keep this module identical in client/gefyra and operator/gefyra.
"""

# ruff: noqa: TRY004 -- invalid configuration values consistently raise ValueError

import json
import re

STOWAWAY_LABELS = {
    "gefyra.dev/app": "stowaway",
    "gefyra.dev/role": "connection",
    "gefyra.dev/provider": "stowaway",
}

_NAME = re.compile(r"[A-Za-z0-9](?:[-A-Za-z0-9_.]*[A-Za-z0-9])?", re.ASCII)
_DNS_LABEL = re.compile(r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?", re.ASCII)


def validate_label_key(key: str, name: str) -> None:
    prefix, separator, suffix = key.rpartition("/")
    label_name = suffix if separator else key
    if not (1 <= len(label_name) <= 63 and _NAME.fullmatch(label_name)):
        raise ValueError(f"{name}: invalid Kubernetes label key {key!r}")
    if separator and (
        not prefix
        or len(prefix) > 253
        or any(
            not (1 <= len(part) <= 63 and _DNS_LABEL.fullmatch(part))
            for part in prefix.split(".")
        )
    ):
        raise ValueError(f"{name}: invalid Kubernetes label key {key!r}")


def validate_label_value(value: str, name: str) -> None:
    if len(value) > 63 or (value and not _NAME.fullmatch(value)):
        raise ValueError(f"{name}: invalid Kubernetes label value {value!r}")


def validate_labels(value: object, name: str, protect_builtin: bool = False) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object mapping strings to strings")
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"{name} must map strings to strings")
        validate_label_key(key, name)
        validate_label_value(item, name)
        if protect_builtin and key in STOWAWAY_LABELS and item != STOWAWAY_LABELS[key]:
            raise ValueError(f"{name}: cannot override Gefyra-managed label {key!r}")


def validate_tolerations(value: object, name: str = "stowaway_tolerations") -> None:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array of Kubernetes toleration objects")
    fields = {"key", "operator", "value", "effect", "tolerationSeconds"}
    for index, item in enumerate(value):
        location = f"{name}[{index}]"
        if not isinstance(item, dict) or item.keys() - fields:
            raise ValueError(
                f"{location}: expected a Kubernetes toleration object with fields {sorted(fields)}"
            )
        for key in fields - {"tolerationSeconds"}:
            if key in item and not isinstance(item[key], str):
                raise ValueError(f"{location}.{key} must be a string")
        key = item.get("key", "")
        operator = item.get("operator", "Equal")
        effect = item.get("effect", "")
        label_value = item.get("value", "")
        if key:
            validate_label_key(key, location)
        if operator not in {"Equal", "Exists"}:
            raise ValueError(f"{location}.operator must be Equal or Exists")
        if not key and operator != "Exists":
            raise ValueError(f"{location}: an empty key requires operator Exists")
        if operator == "Exists" and label_value:
            raise ValueError(f"{location}: operator Exists requires an empty value")
        validate_label_value(label_value, location)
        if effect not in {"", "NoSchedule", "PreferNoSchedule", "NoExecute"}:
            raise ValueError(f"{location}.effect is not a Kubernetes taint effect")
        if "tolerationSeconds" in item:
            seconds = item["tolerationSeconds"]
            if effect != "NoExecute" or type(seconds) is not int:
                raise ValueError(
                    f"{location}.tolerationSeconds requires NoExecute and an integer"
                )
            if not -(2**63) <= seconds < 2**63:
                raise ValueError(
                    f"{location}.tolerationSeconds must fit a Kubernetes int64"
                )


def validate_failure_threshold(value: object) -> None:
    if type(value) is not int or not 1 <= value < 2**31:
        raise ValueError(
            "stowaway_startup_probe_failure_threshold must be an integer between 1 and 2147483647"
        )


def parse_json(value: str, name: str):
    try:
        return json.loads(value)
    except (ValueError, TypeError) as error:
        raise ValueError(f"{name} must contain valid JSON: {error}") from error
