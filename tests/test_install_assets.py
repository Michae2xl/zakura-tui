import stat
import shutil
import subprocess
import textwrap
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


def install_fixture(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    config = repo / "config"
    fake_bin = tmp_path / "fake-bin"
    home = tmp_path / "home"
    scripts.mkdir(parents=True)
    config.mkdir()
    fake_bin.mkdir()
    home.mkdir()

    installer = scripts / "install-local.sh"
    shutil.copy2("scripts/install-local.sh", installer)
    (config / "zakura-tui.example.toml").write_text("[health]\n", "utf-8")

    fake_python = fake_bin / "python3"
    fake_python.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
              mkdir -p "$3/bin"
              cp "$0" "$3/bin/python"
              exit 0
            fi
            if [[ "${1:-}" == "-m" && "${2:-}" == "pip" ]]; then
              touch "$(dirname "$0")/zakura-status"
              touch "$(dirname "$0")/zakura-start"
              chmod +x "$(dirname "$0")/zakura-status" "$(dirname "$0")/zakura-start"
              exit 0
            fi
            exit 2
            """
        ),
        "utf-8",
    )
    fake_python.chmod(0o755)

    environ = {
        "HOME": str(home),
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "XDG_CONFIG_HOME": str(tmp_path / "config-home"),
    }
    return installer, environ


def run_installer(
    installer: Path, environ: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(installer)],
        check=False,
        capture_output=True,
        text=True,
        env=environ,
    )


def test_installer_guides_only_when_local_bin_is_missing_from_path(
    tmp_path: Path,
) -> None:
    installer, environ = install_fixture(tmp_path)

    missing = run_installer(installer, environ)

    assert missing.returncode == 0, missing.stderr
    assert "not currently on PATH" in missing.stdout
    assert 'export PATH="$HOME/.local/bin:$PATH"' in missing.stdout
    assert "shell startup file" in missing.stdout
    home = Path(environ["HOME"])
    assert (home / ".local/bin/zakura-status").is_symlink()
    assert (home / ".local/bin/zakura-start").is_symlink()

    environ["PATH"] = f"{home / '.local/bin'}:{environ['PATH']}"
    present = run_installer(installer, environ)

    assert present.returncode == 0, present.stderr
    assert "not currently on PATH" not in present.stdout
