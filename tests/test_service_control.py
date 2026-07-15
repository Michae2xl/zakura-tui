import subprocess
from pathlib import Path

import pytest

from zakura_tui.config import Config
from zakura_tui.model import ServiceObservation
from zakura_tui.service_control import StartError, ensure_service_started


class StubProbe:
    def __init__(self, observation: ServiceObservation) -> None:
        self.observation = observation

    def poll(self) -> ServiceObservation:
        return self.observation


CONFIG = Config(
    service_name="zakura-pruned",
    health_url="http://127.0.0.1:8231/ready",
    log_path=Path("/tmp/zakurad.log"),
    zakurad_path=Path("/opt/zakurad"),
    zakura_config_path=Path("/etc/zakura.toml"),
    network="Mainnet",
    storage_mode="pruned",
)


def test_active_service_skips_start_command() -> None:
    called = False

    def run(*args, **kwargs):
        nonlocal called
        called = True
        return subprocess.CompletedProcess([], 0, "", "")

    started = ensure_service_started(
        CONFIG,
        service_probe=StubProbe(ServiceObservation(True, True, "active")),
        run=run,
    )
    assert started is False
    assert called is False


def test_inactive_service_runs_exact_argv_without_shell() -> None:
    seen = None

    def run(command, **kwargs):
        nonlocal seen
        seen = (command, kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    started = ensure_service_started(
        CONFIG,
        service_probe=StubProbe(ServiceObservation(True, False, "inactive")),
        run=run,
    )
    assert started is True
    assert seen[0] == ["systemctl", "start", "zakura-pruned"]
    assert seen[1]["shell"] is False


def test_start_failure_is_actionable() -> None:
    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 5, "", "Unit not found")

    with pytest.raises(StartError, match="Unit not found"):
        ensure_service_started(
            CONFIG,
            service_probe=StubProbe(
                ServiceObservation(True, False, "inactive")
            ),
            run=run,
        )


def test_missing_service_never_runs_start_command() -> None:
    called = False

    def run(*args, **kwargs):
        nonlocal called
        called = True
        return subprocess.CompletedProcess([], 0, "", "")

    with pytest.raises(StartError, match="service unit not found: zakura-pruned"):
        ensure_service_started(
            CONFIG,
            service_probe=StubProbe(
                ServiceObservation(False, False, "not-found")
            ),
            run=run,
        )
    assert called is False
