# Installer PATH Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local installer warn users when `~/.local/bin` is not discoverable and document how to activate it temporarily and persistently.

**Architecture:** Keep the existing user-local installation target and add a delimiter-aware `PATH` check after the command links are created. Exercise the real installer in isolated temporary directories with a fake `python3`, then update the README with explicit current-session and future-session guidance.

**Tech Stack:** Bash, Python 3.11+, pytest, standard-library `subprocess` and `pathlib`

---

## File structure

- Modify `scripts/install-local.sh`: detect whether `$HOME/.local/bin` is a complete `PATH` entry and print non-mutating remediation guidance when it is absent.
- Modify `tests/test_install_assets.py`: run the installer in a temporary filesystem and cover both missing and present `PATH` entries.
- Modify `README.md`: separate installation, current-session activation, and persistent shell setup.

### Task 1: Add regression coverage and installer guidance

**Files:**
- Modify: `tests/test_install_assets.py`
- Modify: `scripts/install-local.sh`

- [ ] **Step 1: Write the failing integration test**

Add imports and helpers to `tests/test_install_assets.py`:

```python
import shutil
import subprocess
import textwrap


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


def run_installer(installer: Path, environ: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(installer)],
        check=False,
        capture_output=True,
        text=True,
        env=environ,
    )


def test_installer_guides_only_when_local_bin_is_missing_from_path(tmp_path: Path) -> None:
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
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
.venv/bin/pytest tests/test_install_assets.py::test_installer_guides_only_when_local_bin_is_missing_from_path -v
```

Expected: `FAIL` because the current installer output does not contain `not currently on PATH`.

- [ ] **Step 3: Add the minimal delimiter-aware PATH check**

Append this behavior after the two existing success messages in `scripts/install-local.sh`:

```bash
case ":${PATH:-}:" in
  *":$bin_dir:"*)
    ;;
  *)
    printf '\nWarning: %s is not currently on PATH.\n' "$bin_dir"
    printf '%s\n' 'For this shell session, run:'
    printf '  %s\n' 'export PATH="$HOME/.local/bin:$PATH"'
    printf '%s\n' 'For future shells, add the same export to your shell startup file.'
    printf '%s\n' 'For Bash, use ~/.profile; for other shells, use the appropriate startup file.'
    ;;
esac
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```bash
.venv/bin/pytest tests/test_install_assets.py::test_installer_guides_only_when_local_bin_is_missing_from_path -v
```

Expected: `1 passed`.

- [ ] **Step 5: Validate the shell and installer test file**

Run:

```bash
bash -n scripts/install-local.sh
.venv/bin/pytest tests/test_install_assets.py -v
```

Expected: shell syntax exits `0`; all installer asset tests pass.

- [ ] **Step 6: Commit the tested installer behavior**

```bash
git add scripts/install-local.sh tests/test_install_assets.py
git commit -m "fix: explain missing local bin PATH"
```

### Task 2: Clarify temporary and persistent setup in the README

**Files:**
- Modify: `tests/test_install_assets.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing documentation regression test**

Add to `tests/test_install_assets.py`:

```python
def test_readme_distinguishes_temporary_and_persistent_path_setup() -> None:
    readme = Path("README.md").read_text("utf-8")
    assert "current shell session" in readme
    assert "~/.profile" in readme
    assert "other shells" in readme
```

- [ ] **Step 2: Run the documentation test and verify RED**

Run:

```bash
.venv/bin/pytest tests/test_install_assets.py::test_readme_distinguishes_temporary_and_persistent_path_setup -v
```

Expected: `FAIL` because the current installation section does not distinguish temporary and persistent setup.

- [ ] **Step 3: Replace the README installation instructions**

Replace the current `## Install` code block and its following paragraph with:

````markdown
## Install

```bash
./scripts/install-local.sh
```

The commands are installed in `~/.local/bin`. If that directory is not on
`PATH`, the installer prints a warning. Activate it for the current shell
session with:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

For future Bash sessions, add the same export line to `~/.profile`, then open a
new terminal. Users of other shells should add it to the appropriate shell
startup file.

Edit `~/.config/zakura-tui/config.toml` so the service name and paths match
your local Zakura node installation. Live monitoring and service control
currently require Linux with systemd.
````

- [ ] **Step 4: Run the documentation test and verify GREEN**

Run:

```bash
.venv/bin/pytest tests/test_install_assets.py::test_readme_distinguishes_temporary_and_persistent_path_setup -v
```

Expected: `1 passed`.

- [ ] **Step 5: Run all installer asset tests**

Run:

```bash
.venv/bin/pytest tests/test_install_assets.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit the documentation**

```bash
git add README.md tests/test_install_assets.py
git commit -m "docs: clarify local command PATH setup"
```

### Task 3: Verify the complete change

**Files:**
- Verify: `scripts/install-local.sh`
- Verify: `tests/`
- Verify: repository diff and status

- [ ] **Step 1: Run shell syntax validation**

```bash
bash -n scripts/install-local.sh
```

Expected: exit code `0` with no output.

- [ ] **Step 2: Run the full test suite**

```bash
.venv/bin/pytest -q
```

Expected: all tests pass with no failures.

- [ ] **Step 3: Check whitespace and inspect the complete diff**

```bash
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
git diff origin/main...HEAD
git status -sb
```

Expected: no whitespace errors; only the design, plan, installer, README, and installer tests differ from `origin/main`; the working tree is clean.

### Task 4: Publish a draft pull request

**Files:**
- Publish the existing branch `agent/fix-installer-path-guidance`

- [ ] **Step 1: Confirm GitHub prerequisites and repository target**

```bash
gh --version
gh auth status
gh repo view --json nameWithOwner,defaultBranchRef
```

Expected: authenticated GitHub CLI; repository `Michae2xl/zakura-tui`; default branch `main`.

- [ ] **Step 2: Push the branch with tracking**

```bash
git push -u origin agent/fix-installer-path-guidance
```

Expected: the branch is created on `origin` and tracking is configured.

- [ ] **Step 3: Open a draft PR**

Create a draft PR targeting `main` with:

```text
Title: fix: guide users when local commands are outside PATH

Body:
## What changed

- detect when `~/.local/bin` is missing from `PATH`
- print temporary and persistent remediation guidance
- clarify Bash and other-shell setup in the README
- add isolated installer regression coverage

## Why

The installer could report success while `zakura-status` and `zakura-start`
still failed with `command not found`.

## Validation

- `bash -n scripts/install-local.sh`
- `.venv/bin/pytest -q`
```

Expected: a draft pull request from `agent/fix-installer-path-guidance` into `main`.
