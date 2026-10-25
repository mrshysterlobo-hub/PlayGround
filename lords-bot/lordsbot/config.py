from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class DeviceConfig:
    serial: str | None = None
    adb_path: str = "adb"


@dataclass(frozen=True)
class EngineConfig:
    poll_interval: float = 1.0
    max_runtime: float = 0.0
    start_delay: float = 0.0
    dry_run: bool = False
    template_dir: str = "templates"
    screenshot_dir: str = "screenshots"
    match_threshold: float = 0.88
    scales: tuple[float, ...] = (1.0,)
    max_consecutive_failures: int = 5


@dataclass(frozen=True)
class GuardConfig:
    template: str
    threshold: float | None = None
    cooldown: float = 3.0


@dataclass(frozen=True)
class Config:
    device: DeviceConfig = field(default_factory=DeviceConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    guards: tuple[GuardConfig, ...] = ()
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    source: Path | None = None

    @classmethod
    def load(cls, path: Path | str) -> Config:
        source = Path(path)
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigError(f"could not read config {source}: {exc}") from exc
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {source}: {exc}") from exc
        return cls.from_mapping(raw, source=source)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None, source: Path | None = None) -> Config:
        if data is None:
            data = {}
        data = _as_mapping(data, "config")
        _check_keys(data, {"device", "engine", "guards", "tasks"}, "config")

        device_data = _as_mapping(data.get("device", {}), "device")
        _check_keys(device_data, {"serial", "adb_path"}, "device")
        serial = device_data.get("serial")
        if serial is not None and (not isinstance(serial, str) or not serial.strip()):
            raise ConfigError("device.serial must be a non-empty string or null")
        device = DeviceConfig(
            serial=serial.strip() if isinstance(serial, str) else None,
            adb_path=_string(device_data.get("adb_path", "adb"), "device.adb_path"),
        )

        engine_data = _as_mapping(data.get("engine", {}), "engine")
        _check_keys(
            engine_data,
            {
                "poll_interval",
                "max_runtime",
                "start_delay",
                "dry_run",
                "template_dir",
                "screenshot_dir",
                "match_threshold",
                "scales",
                "max_consecutive_failures",
            },
            "engine",
        )
        engine = EngineConfig(
            poll_interval=_positive_number(engine_data.get("poll_interval", 1.0), "engine.poll_interval"),
            max_runtime=_non_negative_number(engine_data.get("max_runtime", 0.0), "engine.max_runtime"),
            start_delay=_non_negative_number(
                engine_data.get("start_delay", 0.0), "engine.start_delay"
            ),
            dry_run=_bool(engine_data.get("dry_run", False), "engine.dry_run"),
            template_dir=_string(engine_data.get("template_dir", "templates"), "engine.template_dir"),
            screenshot_dir=_string(
                engine_data.get("screenshot_dir", "screenshots"), "engine.screenshot_dir"
            ),
            match_threshold=_threshold(engine_data.get("match_threshold", 0.88), "engine.match_threshold"),
            scales=_scales(engine_data.get("scales", (1.0,))),
            max_consecutive_failures=_positive_int(
                engine_data.get("max_consecutive_failures", 5),
                "engine.max_consecutive_failures",
            ),
        )

        guards_data = data.get("guards", [])
        if not isinstance(guards_data, Sequence) or isinstance(guards_data, (str, bytes)):
            raise ConfigError("guards must be a list")
        guards: list[GuardConfig] = []
        for index, raw_guard in enumerate(guards_data):
            where = f"guards[{index}]"
            guard_data = _as_mapping(raw_guard, where)
            _check_keys(guard_data, {"template", "threshold", "cooldown"}, where)
            if "template" not in guard_data:
                raise ConfigError(f"{where}.template is required")
            guards.append(
                GuardConfig(
                    template=_string(guard_data["template"], f"{where}.template"),
                    threshold=(
                        _threshold(guard_data["threshold"], f"{where}.threshold")
                        if "threshold" in guard_data
                        else None
                    ),
                    cooldown=_non_negative_number(
                        guard_data.get("cooldown", 3.0), f"{where}.cooldown"
                    ),
                )
            )

        tasks_data = _as_mapping(data.get("tasks", {}), "tasks")
        tasks: dict[str, dict[str, Any]] = {}
        for name, options in tasks_data.items():
            if not isinstance(name, str) or not name.strip():
                raise ConfigError("task names must be non-empty strings")
            tasks[name] = dict(_as_mapping(options, f"tasks.{name}"))

        return cls(device=device, engine=engine, guards=tuple(guards), tasks=tasks, source=source)


def _as_mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{where} must be a mapping")
    return value


def _check_keys(data: Mapping[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ConfigError(f"unknown {where} keys: {', '.join(sorted(unknown))}")


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where} must be a non-empty string")
    return value.strip()


def _bool(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{where} must be true or false")
    return value


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{where} must be a number")
    return float(value)


def _positive_number(value: Any, where: str) -> float:
    number = _number(value, where)
    if number <= 0:
        raise ConfigError(f"{where} must be greater than zero")
    return number


def _non_negative_number(value: Any, where: str) -> float:
    number = _number(value, where)
    if number < 0:
        raise ConfigError(f"{where} must be zero or greater")
    return number


def _positive_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"{where} must be a positive integer")
    return value


def _threshold(value: Any, where: str) -> float:
    number = _number(value, where)
    if not 0.0 < number <= 1.0:
        raise ConfigError(f"{where} must be in (0, 1]")
    return number


def _scales(value: Any) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ConfigError("engine.scales must be a non-empty list")
    scales = tuple(_positive_number(scale, "engine.scales") for scale in value)
    return scales
