# Zakura TUI

Live terminal monitoring for a local Zakura node, validated against a running
node on Linux with systemd. `zakura-status` reads the configured service,
health endpoint, node log, and chain tip. The runtime uses only the Python
standard library and terminal-native Unicode/ANSI output.

## Requirements

- Python 3.11 or newer with `venv` support
- Bash for the local installer
- A terminal with ANSI and Unicode support for the best visual experience
- Linux with systemd for live service monitoring and `zakura-start`
- Read access to the configured Zakura log and configuration files

## Install

```bash
./scripts/install-local.sh
export PATH="$HOME/.local/bin:$PATH"
```

Edit `~/.config/zakura-tui/config.toml` so the service name and paths match
your local Zakura node installation. Live monitoring and service control
currently require Linux with systemd.

## Monitor the live node

Start with a single read-only snapshot:

```bash
zakura-status --once --no-color
```

Then open the interactive monitor:

```bash
zakura-status
```

These commands query the configured live node and do not use simulated data.
Exit the interactive monitor with `Ctrl+C`.

## Start if inactive, then monitor

```bash
zakura-start
```

`zakura-start` never restarts an already active service. Configuration lives at
`~/.config/zakura-tui/config.toml`.

## Optional demo mode

Demo mode is only for previewing and validating the terminal interface without
accessing a node:

```bash
zakura-status --demo starting
zakura-status --demo syncing
zakura-status --demo ready
zakura-status --demo degraded
zakura-status --demo stopped
```

Each demo remains open until `Ctrl+C`. Add `--ascii` or `--no-color` to inspect
fallbacks. Demo mode performs no service, health, log, or tip probes.

## Troubleshooting

- `configuration file not found`: run the installer or pass `--config PATH`.
- `WAITING FOR LOG: PATH`: the log does not exist yet; the monitor keeps probing.
- `PERMISSION DENIED: PATH (read permission required)`: grant the current user read access to that path.
- `HEALTH UNAVAILABLE`: the service is active but `/ready` failed after startup grace.
- `SERVICE STOPPED`: the configured systemd unit is inactive; use `zakura-start`.
- `service unit not found: NAME`: correct `service_name`; no start command was run.
- `TIP FALLBACK FAILED: PATH`: verify `zakurad_path` and `zakura_config_path`.
