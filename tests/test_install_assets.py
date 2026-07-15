import stat
from pathlib import Path

from zakura_tui.config import load_config


def test_example_config_uses_portable_defaults() -> None:
    path = Path("config/zakura-tui.example.toml")
    config = load_config(path, environ={})
    assert config.service_name == "zakura-pruned"
    assert config.health_url == "http://127.0.0.1:8231/ready"
    assert config.log_path == Path("/var/log/zakura/zakurad.log")
    assert config.zakurad_path == Path("/usr/local/bin/zakurad")
    assert config.zakura_config_path == Path("/etc/zakura/zakura.toml")
    assert config.network == "Mainnet"
    assert config.storage_mode == "pruned"


def test_installer_is_executable_and_troubleshooting_is_shipped() -> None:
    installer = Path("scripts/install-local.sh")
    assert installer.stat().st_mode & stat.S_IXUSR
    readme = Path("README.md").read_text("utf-8")
    for label in (
        "WAITING FOR LOG",
        "PERMISSION DENIED",
        "HEALTH UNAVAILABLE",
        "SERVICE STOPPED",
        "TIP FALLBACK FAILED",
    ):
        assert label in readme
