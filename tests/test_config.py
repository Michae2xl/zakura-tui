from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from zakura_tui.config import ConfigError, load_config


BASE_TOML = """
service_name = "zakura-pruned"
health_url = "http://127.0.0.1:8231/ready"
log_path = "/tmp/zakurad.log"
zakurad_path = "/opt/zakura/bin/zakurad"
zakura_config_path = "/etc/zakura/zakura.toml"
network = "Mainnet"
storage_mode = "pruned"
refresh_seconds = 2.0
startup_grace_seconds = 15.0
health_stale_seconds = 10.0
tip_timeout_seconds = 15.0
start_command = ["systemctl", "start", "zakura-pruned"]
"""

INTERVAL_FIELDS = (
    "refresh_seconds",
    "startup_grace_seconds",
    "health_stale_seconds",
    "tip_timeout_seconds",
)


def write_config(tmp_path: Path, text: str = BASE_TOML) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def replace_toml_value(text: str, name: str, value: str) -> str:
    prefix = f"{name} = "
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{name} = {value}"
            return "\n".join(lines)
    raise AssertionError(f"missing test fixture field: {name}")


def test_loads_typed_toml(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path), environ={})
    assert config.service_name == "zakura-pruned"
    assert config.log_path == Path("/tmp/zakurad.log")
    assert config.start_command == ("systemctl", "start", "zakura-pruned")
    assert config.storage_mode == "pruned"


def test_environment_overrides_file(tmp_path: Path) -> None:
    config = load_config(
        write_config(tmp_path),
        environ={
            "ZAKURA_TUI_REFRESH_SECONDS": "0.5",
            "ZAKURA_TUI_START_COMMAND": "systemctl start alternate-zakura",
        },
    )
    assert config.refresh_seconds == 0.5
    assert config.start_command == ("systemctl", "start", "alternate-zakura")


def test_explicit_overrides_win(tmp_path: Path) -> None:
    config = load_config(
        write_config(tmp_path),
        environ={"ZAKURA_TUI_NETWORK": "Testnet"},
        overrides={"network": "Regtest"},
    )
    assert config.network == "Regtest"


def test_explicit_empty_environment_is_isolated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZAKURA_TUI_NETWORK", "Testnet")
    config = load_config(write_config(tmp_path), environ={})
    assert config.network == "Mainnet"


@pytest.mark.parametrize("value", [0.0, 0.1, 61.0])
def test_rejects_unsafe_refresh_interval(tmp_path: Path, value: float) -> None:
    with pytest.raises(ConfigError, match="refresh_seconds"):
        load_config(
            write_config(tmp_path),
            environ={"ZAKURA_TUI_REFRESH_SECONDS": str(value)},
        )


def test_reports_missing_required_field(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="health_url"):
        load_config(write_config(tmp_path, 'service_name = "zakura"'), environ={})


def test_rejects_string_start_command(tmp_path: Path) -> None:
    text = BASE_TOML.replace(
        'start_command = ["systemctl", "start", "zakura-pruned"]',
        'start_command = "systemctl start zakura-pruned"',
    )
    with pytest.raises(ConfigError, match="start_command must be an array"):
        load_config(write_config(tmp_path, text), environ={})


def test_rejects_non_numeric_toml_interval(tmp_path: Path) -> None:
    text = BASE_TOML.replace("refresh_seconds = 2.0", 'refresh_seconds = "fast"')
    with pytest.raises(ConfigError, match="refresh_seconds must be numeric"):
        load_config(write_config(tmp_path, text), environ={})


@pytest.mark.parametrize(
    "name", ["service_name", "health_url", "network", "storage_mode"]
)
@pytest.mark.parametrize("value", ["7", '""', '"   "'])
def test_rejects_invalid_required_text(
    tmp_path: Path, name: str, value: str
) -> None:
    text = replace_toml_value(BASE_TOML, name, value)
    with pytest.raises(ConfigError, match=rf"{name} must be a nonempty string"):
        load_config(write_config(tmp_path, text), environ={})


@pytest.mark.parametrize("name", ["log_path", "zakurad_path", "zakura_config_path"])
def test_rejects_non_path_required_values(tmp_path: Path, name: str) -> None:
    text = replace_toml_value(BASE_TOML, name, "false")
    with pytest.raises(ConfigError, match=rf"{name} must be a string or Path"):
        load_config(write_config(tmp_path, text), environ={})


@pytest.mark.parametrize("name", ["log_path", "zakurad_path", "zakura_config_path"])
def test_rejects_empty_required_paths(tmp_path: Path, name: str) -> None:
    text = replace_toml_value(BASE_TOML, name, '"   "')
    with pytest.raises(ConfigError, match=rf"{name} must not be empty"):
        load_config(write_config(tmp_path, text), environ={})


def test_accepts_path_override(tmp_path: Path) -> None:
    expected = tmp_path / "zakurad.log"
    config = load_config(
        write_config(tmp_path), environ={}, overrides={"log_path": expected}
    )
    assert config.log_path == expected


@pytest.mark.parametrize("name", INTERVAL_FIELDS)
def test_rejects_boolean_intervals(tmp_path: Path, name: str) -> None:
    with pytest.raises(ConfigError, match=rf"{name} must be numeric"):
        load_config(write_config(tmp_path), environ={}, overrides={name: True})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("refresh_seconds", float("nan")),
        ("startup_grace_seconds", float("inf")),
        ("health_stale_seconds", float("-inf")),
        ("tip_timeout_seconds", float("nan")),
    ],
)
def test_rejects_non_finite_intervals(
    tmp_path: Path, name: str, value: float
) -> None:
    with pytest.raises(ConfigError, match=rf"{name} must be finite"):
        load_config(write_config(tmp_path), environ={}, overrides={name: value})


def test_rejects_non_finite_environment_interval(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="refresh_seconds must be finite"):
        load_config(
            write_config(tmp_path),
            environ={"ZAKURA_TUI_REFRESH_SECONDS": "nan"},
        )


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        (
            "startup_grace_seconds",
            -0.1,
            "startup_grace_seconds must be non-negative",
        ),
        ("health_stale_seconds", 0.0, "health_stale_seconds must be positive"),
        ("tip_timeout_seconds", 0.0, "tip_timeout_seconds must be positive"),
    ],
)
def test_reports_specific_interval_error(
    tmp_path: Path, name: str, value: float, message: str
) -> None:
    with pytest.raises(ConfigError, match=rf"^{message}$"):
        load_config(write_config(tmp_path), environ={}, overrides={name: value})


def test_accepts_zero_startup_grace(tmp_path: Path) -> None:
    config = load_config(
        write_config(tmp_path),
        environ={},
        overrides={"startup_grace_seconds": 0.0},
    )
    assert config.startup_grace_seconds == 0.0


@pytest.mark.parametrize("url", ["ftp://example.com/ready", "ready"])
def test_rejects_non_http_health_url(tmp_path: Path, url: str) -> None:
    with pytest.raises(
        ConfigError, match=r"health_url must be an absolute HTTP\(S\) URL"
    ):
        load_config(
            write_config(tmp_path), environ={}, overrides={"health_url": url}
        )


@pytest.mark.parametrize("url", ["http:///ready", "http://:8231/ready"])
def test_rejects_health_url_without_hostname(tmp_path: Path, url: str) -> None:
    with pytest.raises(ConfigError, match="health_url must include a hostname"):
        load_config(
            write_config(tmp_path), environ={}, overrides={"health_url": url}
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://[::1/ready",
        "http://[not-an-ipv6-address]/ready",
        "http://127.0.0.1:/ready",
        "http://127.0.0.1:8231:9/ready",
        "http://127.0.0.1:not-a-port/ready",
        "http://127.0.0.1:65536/ready",
    ],
)
def test_normalizes_malformed_health_url(tmp_path: Path, url: str) -> None:
    with pytest.raises(ConfigError, match="health_url is invalid"):
        load_config(
            write_config(tmp_path), environ={}, overrides={"health_url": url}
        )


def test_normalizes_invalid_utf8(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_bytes(b"\xff")
    with pytest.raises(ConfigError, match="configuration must be valid UTF-8"):
        load_config(path, environ={})


def test_reports_invalid_toml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(write_config(tmp_path, "service_name = ["), environ={})


def test_normalizes_config_path_expansion_error(monkeypatch, tmp_path: Path) -> None:
    path = write_config(tmp_path)
    original_expanduser = Path.expanduser

    def expanduser(candidate: Path) -> Path:
        if candidate == path:
            raise RuntimeError("home directory unavailable")
        return original_expanduser(candidate)

    monkeypatch.setattr(Path, "expanduser", expanduser)
    with pytest.raises(ConfigError, match="configuration path cannot be expanded"):
        load_config(path, environ={})


def test_normalizes_configured_path_expansion_error(
    monkeypatch, tmp_path: Path
) -> None:
    failing_path = Path("/tmp/zakurad.log")
    original_expanduser = Path.expanduser

    def expanduser(candidate: Path) -> Path:
        if candidate == failing_path:
            raise RuntimeError("home directory unavailable")
        return original_expanduser(candidate)

    monkeypatch.setattr(Path, "expanduser", expanduser)
    with pytest.raises(ConfigError, match="log_path cannot be expanded"):
        load_config(write_config(tmp_path), environ={})


def test_normalizes_malformed_environment_command(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="start_command has invalid shell quoting"):
        load_config(
            write_config(tmp_path),
            environ={"ZAKURA_TUI_START_COMMAND": 'systemctl start "unterminated'},
        )


def test_reports_field_for_invalid_numeric_environment_value(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="refresh_seconds must be numeric"):
        load_config(
            write_config(tmp_path),
            environ={"ZAKURA_TUI_REFRESH_SECONDS": "fast"},
        )


def test_config_is_frozen(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path), environ={})
    with pytest.raises(FrozenInstanceError):
        config.network = "Testnet"  # type: ignore[misc]
