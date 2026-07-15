from pathlib import Path

import zakura_tui.cli as cli
from zakura_tui.cli import status_main
from zakura_tui.config import Config, ConfigError
from zakura_tui.demo import demo_snapshot
from zakura_tui.model import NodeState
from zakura_tui.service_control import StartError


def test_all_demo_states_are_deterministic() -> None:
    expected = {
        "starting": NodeState.STARTING,
        "syncing": NodeState.SYNCING,
        "ready": NodeState.READY,
        "degraded": NodeState.DEGRADED,
        "stopped": NodeState.STOPPED,
    }
    assert {name: demo_snapshot(name).state for name in expected} == expected


def test_demo_once_does_not_require_config(capsys, tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    result = status_main(
        [
            "--demo",
            "ready",
            "--once",
            "--no-color",
            "--config",
            str(missing),
        ]
    )
    output = capsys.readouterr().out
    assert result == 0
    assert "SYNCHRONIZED" in output
    assert "3413390" in output.replace(",", "")
    assert "\x1b[?1049h" not in output


def test_live_mode_reports_missing_config(capsys, tmp_path: Path) -> None:
    result = status_main(["--once", "--config", str(tmp_path / "missing.toml")])
    assert result == 2
    assert "configuration file not found" in capsys.readouterr().err


def test_interactive_demo_requires_a_tty(capsys) -> None:
    result = status_main(["--demo", "ready", "--no-color"])
    assert result == 2
    assert (
        "interactive mode requires a TTY; use --once"
        in capsys.readouterr().err
    )


def cli_config(tmp_path: Path) -> Config:
    return Config(
        service_name="zakura-pruned",
        health_url="http://127.0.0.1:8231/ready",
        log_path=tmp_path / "zakurad.log",
        zakurad_path=tmp_path / "zakurad",
        zakura_config_path=tmp_path / "zakura.toml",
        network="Mainnet",
        storage_mode="pruned",
    )


def test_start_reports_configuration_error(monkeypatch, capsys) -> None:
    def fail(_path):
        raise ConfigError("bad config")

    monkeypatch.setattr(cli, "load_config", fail)
    assert cli.start_main(["--once"]) == 2
    assert "zakura-start: bad config" in capsys.readouterr().err


def test_start_reports_service_error(monkeypatch, capsys, tmp_path: Path) -> None:
    config = cli_config(tmp_path)
    monkeypatch.setattr(cli, "load_config", lambda _path: config)

    def fail(_config):
        raise StartError("Unit not found")

    monkeypatch.setattr(cli, "ensure_service_started", fail)
    assert cli.start_main(["--once"]) == 3
    assert "zakura-start: Unit not found" in capsys.readouterr().err


def test_start_delegates_to_monitor_once(monkeypatch, tmp_path: Path) -> None:
    config = cli_config(tmp_path)
    monitor = object()
    calls: list[tuple[object, dict[str, object]]] = []
    monkeypatch.setattr(cli, "load_config", lambda _path: config)
    monkeypatch.setattr(cli, "ensure_service_started", lambda _config: False)
    monkeypatch.setattr(cli, "NodeMonitor", lambda _config: monitor)

    def fake_run_monitor(received, **kwargs):
        calls.append((received, kwargs))
        return 0

    monkeypatch.setattr(cli, "run_monitor", fake_run_monitor)
    assert cli.start_main(["--once", "--no-color"]) == 0
    assert calls == [
        (
            monitor,
            {
                "network": "Mainnet",
                "storage_mode": "pruned",
                "refresh_seconds": 2.0,
                "once": True,
                "no_color": True,
                "force_ascii": False,
            },
        )
    ]


def test_start_reports_unexpected_monitor_error(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    config = cli_config(tmp_path)
    monkeypatch.setattr(cli, "load_config", lambda _path: config)
    monkeypatch.setattr(cli, "ensure_service_started", lambda _config: False)
    monkeypatch.setattr(cli, "NodeMonitor", lambda _config: object())

    def fail(*args, **kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr(cli, "run_monitor", fail)
    assert cli.start_main(["--once"]) == 1
    assert "zakura-start: render failed" in capsys.readouterr().err
