from __future__ import annotations

import subprocess
from typing import Callable

from .config import Config
from .probes import ServiceProbe


class StartError(RuntimeError):
    """Raised when the configured service cannot be started."""


def ensure_service_started(
    config: Config,
    *,
    service_probe: ServiceProbe | None = None,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> bool:
    observation = (service_probe or ServiceProbe(config.service_name)).poll()
    if observation.active:
        return False
    if not observation.exists:
        raise StartError(f"service unit not found: {config.service_name}")
    try:
        result = run(
            list(config.start_command),
            capture_output=True,
            text=True,
            timeout=30.0,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StartError(f"cannot run start command: {error}") from error
    if result.returncode != 0:
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit {result.returncode}"
        )
        raise StartError(f"cannot start {config.service_name}: {detail}")
    return True
