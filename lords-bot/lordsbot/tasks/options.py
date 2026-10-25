from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def as_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def as_string_list(value: Any, name: str) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = list(value)
    else:
        raise TypeError(f"{name} must be a string or a list of strings")
    if not values:
        raise ValueError(f"{name} must not be empty")
    return [as_string(item, name) for item in values]


def as_positive_int(value: Any, name: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def as_positive_float(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return float(value)


def as_non_negative_float(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{name} must be zero or greater")
    return float(value)


def resolve_templates(
    defaults: Mapping[str, str],
    overrides: Mapping[str, str] | None,
) -> dict[str, str]:
    if overrides is None:
        return dict(defaults)
    if not isinstance(overrides, Mapping):
        raise TypeError("templates must be a mapping")
    unknown = set(overrides) - set(defaults)
    if unknown:
        raise ValueError(f"unknown template keys: {', '.join(sorted(unknown))}")
    resolved = dict(defaults)
    for key, value in overrides.items():
        resolved[key] = as_string(value, f"templates.{key}")
    return resolved
