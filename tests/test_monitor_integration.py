import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from zakura_tui.config import Config
from zakura_tui.model import NodeState, ServiceObservation, TipObservation
from zakura_tui.monitor import NodeMonitor


class StubProbe:
    def __init__(self, value):
        self.value = value

    def poll(self):
        return self.value


CONFIG = Config(
    service_name="zakura-pruned",
    health_url="http://127.0.0.1:8231/ready",
    log_path=Path("/tmp/zakurad.log"),
    zakurad_path=Path("/opt/zakurad"),
    zakura_config_path=Path("/etc/zakura.toml"),
    network="Mainnet",
    storage_mode="pruned",
)


class ReadyHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args: object) -> None:
        return None


@pytest.fixture
def ready_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ReadyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/ready"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)


def test_real_log_and_health_probe_resolve_ready(
    tmp_path: Path, ready_url: str
) -> None:
    log_path = tmp_path / "zakurad.log"
    log_path.write_text(
        "2026-07-15T17:02:23Z sync_percent=100.000% "
        "current_height=Height(3413390) network_upgrade=Nu6_2 "
        "remaining_sync_blocks=0\n",
        encoding="utf-8",
    )
    config = replace(CONFIG, health_url=ready_url, log_path=log_path)
    monitor = NodeMonitor(
        config,
        service_probe=StubProbe(ServiceObservation(True, True, "active")),
        tip_probe=StubProbe(TipObservation(None, None, 100.0)),
    )
    try:
        snapshot = monitor.poll()
    finally:
        monitor.close()
    assert snapshot.state is NodeState.READY
    assert snapshot.sync.current_height == 3_413_390
    assert snapshot.health is not None and snapshot.health.detail == "ok"
