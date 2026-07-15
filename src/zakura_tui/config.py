from __future__ import annotations

import math
import os
import shlex
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when monitor configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    service_name: str
    health_url: str
    log_path: Path
    zakurad_path: Path
    zakura_config_path: Path
    network: str
    storage_mode: str
    refresh_seconds: float = 2.0
    startup_grace_seconds: float = 15.0
    health_stale_seconds: float = 10.0
    tip_timeout_seconds: float = 15.0
    start_command: tuple[str, ...] = ("systemctl", "start", "zakura-pruned")


TEXT_FIELDS = (
    "service_name",
    "health_url",
    "network",
    "storage_mode",
)
PATH_FIELDS = (
    "log_path",
    "zakurad_path",
    "zakura_config_path",
)
REQUIRED = frozenset((*TEXT_FIELDS, *PATH_FIELDS))
FLOAT_FIELDS = (
    "refresh_seconds",
    "startup_grace_seconds",
    "health_stale_seconds",
    "tip_timeout_seconds",
)


def default_config_path() -> Path:
    return Path.home() / ".config" / "zakura-tui" / "config.toml"


def _environment_values(environ: Mapping[str, str]) -> dict[str, object]:
    values: dict[str, object] = {}
    for field in fields(Config):
        key = f"ZAKURA_TUI_{field.name.upper()}"
        if key not in environ:
            continue
        raw = environ[key]
        if field.name == "start_command":
            try:
                values[field.name] = tuple(shlex.split(raw))
            except (TypeError, ValueError) as error:
                raise ConfigError(
                    "start_command has invalid shell quoting"
                ) from error
        else:
            values[field.name] = raw
    return values


def _expand_config_path(path: str | Path | None) -> Path:
    if path is not None and not isinstance(path, (str, Path)):
        raise ConfigError("configuration path must be a string or Path")

    try:
        config_path = default_config_path() if path is None else Path(path)
        return config_path.expanduser()
    except (OSError, RuntimeError) as error:
        raise ConfigError("configuration path cannot be expanded") from error


def _read_config(config_path: Path) -> dict[str, object]:
    try:
        text = config_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError("configuration must be valid UTF-8") from error
    except OSError as error:
        raise ConfigError(
            f"cannot read configuration {config_path}: {error}"
        ) from error

    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(
            f"invalid TOML in configuration {config_path}: {error}"
        ) from error


def _normalize_required_fields(data: dict[str, object]) -> None:
    missing = sorted(REQUIRED - data.keys())
    if missing:
        raise ConfigError(f"missing required configuration: {', '.join(missing)}")

    for name in TEXT_FIELDS:
        value = data[name]
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{name} must be a nonempty string")

    for name in PATH_FIELDS:
        value = data[name]
        if not isinstance(value, (str, Path)):
            raise ConfigError(f"{name} must be a string or Path")
        if not str(value).strip():
            raise ConfigError(f"{name} must not be empty")
        try:
            data[name] = Path(value).expanduser()
        except (OSError, RuntimeError, ValueError) as error:
            raise ConfigError(f"{name} cannot be expanded") from error


def _normalize_intervals(data: dict[str, object]) -> None:
    for name in FLOAT_FIELDS:
        if name not in data:
            continue
        value = data[name]
        if isinstance(value, bool):
            raise ConfigError(f"{name} must be numeric")
        try:
            interval = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError) as error:
            raise ConfigError(f"{name} must be numeric") from error
        if not math.isfinite(interval):
            raise ConfigError(f"{name} must be finite")
        data[name] = interval


def _normalize_start_command(data: dict[str, object]) -> None:
    command = data.get("start_command", ("systemctl", "start", "zakura-pruned"))
    if not isinstance(command, (list, tuple)) or not all(
        isinstance(part, str) for part in command
    ):
        raise ConfigError("start_command must be an array of strings")
    if not command:
        raise ConfigError("start_command must not be empty")
    data["start_command"] = tuple(command)


def _validate_health_url(health_url: str) -> None:
    try:
        parsed_url = urlparse(health_url)
    except (TypeError, ValueError) as error:
        raise ConfigError("health_url is invalid") from error

    if parsed_url.scheme not in {"http", "https"}:
        raise ConfigError("health_url must be an absolute HTTP(S) URL")

    authority = parsed_url.netloc
    if any(
        ord(character) <= 0x20 or ord(character) == 0x7F
        for character in authority
    ):
        raise ConfigError("health_url is invalid")

    try:
        hostname = parsed_url.hostname
        _ = parsed_url.port
    except ValueError as error:
        raise ConfigError("health_url is invalid") from error

    if not hostname or not hostname.strip():
        raise ConfigError("health_url must include a hostname")

    if authority.rsplit("@", 1)[-1].endswith(":"):
        raise ConfigError("health_url is invalid")


def load_config(
    path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    overrides: Mapping[str, object] | None = None,
) -> Config:
    config_path = _expand_config_path(path)
    try:
        config_exists = config_path.is_file()
    except OSError as error:
        raise ConfigError(
            f"cannot access configuration {config_path}: {error}"
        ) from error
    if not config_exists:
        raise ConfigError(f"configuration file not found: {config_path}")

    data = _read_config(config_path)
    data.update(_environment_values(os.environ if environ is None else environ))
    data.update(overrides or {})

    _normalize_required_fields(data)
    _normalize_intervals(data)
    _normalize_start_command(data)

    try:
        config = Config(**data)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ConfigError(f"invalid configuration: {error}") from error

    _validate_health_url(config.health_url)
    if not 0.2 <= config.refresh_seconds <= 60.0:
        raise ConfigError("refresh_seconds must be between 0.2 and 60.0")
    if config.startup_grace_seconds < 0:
        raise ConfigError("startup_grace_seconds must be non-negative")
    if config.health_stale_seconds <= 0:
        raise ConfigError("health_stale_seconds must be positive")
    if config.tip_timeout_seconds <= 0:
        raise ConfigError("tip_timeout_seconds must be positive")
    return config
