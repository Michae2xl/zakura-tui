import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

from zakura_tui.config import Config
from zakura_tui.model import (
    HealthObservation,
    NodeState,
    ServiceObservation,
    TipObservation,
)
from zakura_tui.monitor import NodeMonitor


class StubProbe:
    def __init__(self, value):
        self.value = value

    def poll(self):
        return self.value


class StubLogReader:
    def __init__(self, lines: list[str]):
        self.lines = lines

    def poll(self) -> list[str]:
        lines, self.lines = self.lines, []
        return lines


CONFIG = Config(
    service_name="zakura-pruned",
    health_url="http://127.0.0.1:8231/ready",
    log_path=Path("/tmp/zakurad.log"),
    zakurad_path=Path("/opt/zakurad"),
    zakura_config_path=Path("/etc/zakura.toml"),
    network="Mainnet",
    storage_mode="pruned",
)


def test_poll_merges_log_and_health_into_ready_snapshot() -> None:
    monitor = NodeMonitor(
        CONFIG,
        service_probe=StubProbe(ServiceObservation(True, True, "active")),
        health_probe=StubProbe(HealthObservation(True, True, "ok", 100.0)),
        tip_probe=StubProbe(TipObservation(None, None, 100.0)),
        log_reader=StubLogReader(
            [
                "2026-07-15T17:02:23Z sync_percent=100.000% "
                "current_height=Height(3413390) network_upgrade=Nu6_2 "
                "remaining_sync_blocks=0"
            ]
        ),
        clock=lambda: 100.0,
    )
    snapshot = monitor.poll()
    monitor.close()
    assert snapshot.state is NodeState.READY
    assert snapshot.sync.current_height == 3_413_390
    assert snapshot.sync.remaining_blocks == 0


def test_first_poll_does_not_wait_for_slow_tip_probe() -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingTip:
        def poll(self):
            entered.set()
            release.wait(timeout=1.0)
            return TipObservation(None, "test released", 100.0)

    monitor = NodeMonitor(
        CONFIG,
        service_probe=StubProbe(ServiceObservation(True, True, "active")),
        health_probe=StubProbe(HealthObservation(True, False, "503", 100.0)),
        tip_probe=BlockingTip(),
        log_reader=StubLogReader([]),
        clock=lambda: 100.0,
    )
    try:
        started = time.monotonic()
        snapshot = monitor.poll()
        elapsed = time.monotonic() - started
        assert snapshot.state is NodeState.STARTING
        assert elapsed < 0.2
        assert entered.wait(timeout=0.2)
    finally:
        release.set()
        monitor.close()


def test_close_does_not_wait_for_running_tip_probe() -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingTip:
        def poll(self):
            entered.set()
            release.wait(timeout=1.0)
            return TipObservation(None, None, 100.0)

    monitor = NodeMonitor(
        CONFIG,
        service_probe=StubProbe(ServiceObservation(True, True, "active")),
        health_probe=StubProbe(HealthObservation(True, False, "503", 100.0)),
        tip_probe=BlockingTip(),
        log_reader=StubLogReader([]),
        clock=lambda: 100.0,
    )
    monitor.poll()
    assert entered.wait(timeout=0.2)
    started = time.monotonic()
    monitor.close()
    elapsed = time.monotonic() - started
    release.set()
    assert elapsed < 0.1


class ErrorLogReader:
    def __init__(self, error: OSError):
        self.error = error

    def poll(self) -> list[str]:
        raise self.error


@pytest.mark.parametrize(
    ("error", "label"),
    [
        (FileNotFoundError("missing"), "WAITING FOR LOG"),
        (PermissionError("denied"), "PERMISSION DENIED"),
    ],
)
def test_log_errors_are_visible_without_filesystem_mutation(
    tmp_path: Path, error: OSError, label: str
) -> None:
    log_path = tmp_path / "zakurad.log"
    config = replace(CONFIG, log_path=log_path)
    monitor = NodeMonitor(
        config,
        service_probe=StubProbe(ServiceObservation(True, True, "active")),
        health_probe=StubProbe(HealthObservation(True, False, "503", 100.0)),
        tip_probe=StubProbe(TipObservation(None, None, 100.0)),
        log_reader=ErrorLogReader(error),
        clock=lambda: 100.0,
    )
    try:
        snapshot = monitor.poll()
    finally:
        monitor.close()
    assert snapshot.state is NodeState.STARTING
    assert any(
        label in item and str(log_path) in item for item in snapshot.diagnostics
    )
    assert not log_path.exists()


def test_tip_failure_names_the_configured_binary() -> None:
    entered = threading.Event()
    release = threading.Event()

    class MissingTip:
        def poll(self):
            entered.set()
            release.wait(timeout=1.0)
            return TipObservation(None, "No such file or directory", 100.0)

    monitor = NodeMonitor(
        CONFIG,
        service_probe=StubProbe(ServiceObservation(True, True, "active")),
        health_probe=StubProbe(HealthObservation(True, False, "503", 100.0)),
        tip_probe=MissingTip(),
        log_reader=StubLogReader([]),
        clock=lambda: 100.0,
    )
    try:
        monitor.poll()
        assert entered.wait(timeout=0.2)
        release.set()
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            snapshot = monitor.poll()
            if snapshot.diagnostics:
                break
            time.sleep(0.01)
        assert any(
            "TIP FALLBACK FAILED" in item and str(CONFIG.zakurad_path) in item
            for item in snapshot.diagnostics
        )
    finally:
        release.set()
        monitor.close()
