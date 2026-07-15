#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv="$repo_root/.venv"
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/zakura-tui"
bin_dir="$HOME/.local/bin"

python3 -m venv "$venv"
"$venv/bin/python" -m pip install --no-deps -e "$repo_root"
mkdir -p "$config_dir" "$bin_dir"
if [[ ! -f "$config_dir/config.toml" ]]; then
  install -m 600 "$repo_root/config/zakura-tui.example.toml" "$config_dir/config.toml"
fi
ln -sfn "$venv/bin/zakura-status" "$bin_dir/zakura-status"
ln -sfn "$venv/bin/zakura-start" "$bin_dir/zakura-start"

printf 'Installed zakura-status and zakura-start in %s\n' "$bin_dir"
printf 'Configuration: %s/config.toml\n' "$config_dir"
