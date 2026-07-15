import subprocess
from pathlib import Path

from zakura_tui.probes import HealthProbe, ServiceProbe, TipHeightProbe


def completed(
    stdout: str, returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def test_service_probe_reads_systemd_properties() -> None:
    probe = ServiceProbe(
        "zakura-pruned",
        run=lambda *args, **kwargs: completed(
            "LoadState=loaded\nActiveState=active\n"
        ),
    )
    result = probe.poll()
    assert result.exists is True
    assert result.active is True
    assert result.detail == "active"


def test_service_probe_reports_missing_unit() -> None:
    probe = ServiceProbe(
        "missing",
        run=lambda *args, **kwargs: completed(
            "LoadState=not-found\nActiveState=inactive\n"
        ),
    )
    result = probe.poll()
    assert result.exists is False
    assert result.active is False


def test_service_probe_preserves_failed_state() -> None:
    probe = ServiceProbe(
        "failed",
        run=lambda *args, **kwargs: completed(
            "LoadState=loaded\nActiveState=failed\n"
        ),
    )
    result = probe.poll()
    assert result.exists is True
    assert result.active is False
    assert result.detail == "failed"


class FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b"ok") -> None:
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


def test_health_probe_accepts_only_200_ok() -> None:
    probe = HealthProbe(
        "http://127.0.0.1:8231/ready",
        timeout=1.0,
        opener=lambda *args, **kwargs: FakeResponse(),
        clock=lambda: 12.5,
    )
    result = probe.poll()
    assert result.reachable is True
    assert result.ready is True
    assert result.observed_at == 12.5


def test_health_probe_rejects_invalid_body_and_status() -> None:
    for response in (FakeResponse(body=b"syncing"), FakeResponse(status=503)):
        result = HealthProbe(
            "http://127.0.0.1:8231/ready",
            timeout=1.0,
            opener=lambda *args, response=response, **kwargs: response,
        ).poll()
        assert result.reachable is True
        assert result.ready is False


def test_tip_probe_uses_exact_zakurad_command() -> None:
    seen: list[str] = []

    def run(command, **kwargs):
        seen.extend(command)
        return completed("3413390\n")

    probe = TipHeightProbe(
        zakurad_path=Path("/opt/zakura/bin/zakurad"),
        config_path=Path("/etc/zakura/zakura.toml"),
        network="Mainnet",
        timeout=15.0,
        run=run,
        clock=lambda: 20.0,
    )
    result = probe.poll()
    assert result.height == 3_413_390
    assert seen == [
        "/opt/zakura/bin/zakurad",
        "-c",
        "/etc/zakura/zakura.toml",
        "tip-height",
        "--network",
        "Mainnet",
    ]


def test_health_timeout_is_unreachable() -> None:
    def timeout(*args, **kwargs):
        raise TimeoutError("slow")

    result = HealthProbe(
        "http://127.0.0.1/ready", timeout=1, opener=timeout
    ).poll()
    assert result.reachable is False
    assert "slow" in result.detail


def test_invalid_tip_output_is_an_error() -> None:
    probe = TipHeightProbe(
        zakurad_path=Path("zakurad"),
        config_path=Path("zakura.toml"),
        network="Mainnet",
        timeout=1,
        run=lambda *args, **kwargs: completed("not-a-height\n"),
    )
    result = probe.poll()
    assert result.height is None
    assert result.error is not None and "invalid literal" in result.error
