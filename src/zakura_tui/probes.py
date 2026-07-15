from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .model import HealthObservation, ServiceObservation, TipObservation


Run = Callable[..., subprocess.CompletedProcess[str]]
Open = Callable[..., object]


class ServiceProbe:
    def __init__(self, service_name: str, *, run: Run = subprocess.run) -> None:
        self.service_name = service_name
        self._run = run

    def poll(self) -> ServiceObservation:
        command = [
            "systemctl",
            "show",
            self.service_name,
            "--property=LoadState",
            "--property=ActiveState",
            "--no-pager",
        ]
        try:
            result = self._run(
                command,
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return ServiceObservation(False, False, f"systemd unavailable: {error}")
        values = dict(
            line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
        )
        load = values.get("LoadState", "not-found")
        active_state = values.get("ActiveState", "inactive")
        return ServiceObservation(
            exists=load != "not-found",
            active=load != "not-found" and active_state == "active",
            detail=active_state,
        )


class HealthProbe:
    def __init__(
        self,
        url: str,
        *,
        timeout: float,
        opener: Open = urlopen,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self._opener = opener
        self._clock = clock

    def poll(self) -> HealthObservation:
        observed_at = self._clock()
        request = Request(self.url, headers={"User-Agent": "zakura-tui/0.1"})
        try:
            with self._opener(  # type: ignore[attr-defined]
                request, timeout=self.timeout
            ) as response:
                body = response.read(128).decode("utf-8", "replace").strip().lower()
                status = response.status
            return HealthObservation(
                True, status == 200 and body == "ok", body, observed_at
            )
        except HTTPError as error:
            return HealthObservation(
                True, False, f"HTTP {error.code}", observed_at
            )
        except (URLError, TimeoutError, OSError) as error:
            return HealthObservation(False, False, str(error), observed_at)


class TipHeightProbe:
    def __init__(
        self,
        *,
        zakurad_path: Path,
        config_path: Path,
        network: str,
        timeout: float,
        run: Run = subprocess.run,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.command = [
            str(zakurad_path),
            "-c",
            str(config_path),
            "tip-height",
            "--network",
            network,
        ]
        self.timeout = timeout
        self._run = run
        self._clock = clock

    def poll(self) -> TipObservation:
        observed_at = self._clock()
        try:
            result = self._run(
                self.command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or f"exit {result.returncode}"
                return TipObservation(None, detail, observed_at)
            return TipObservation(int(result.stdout.strip()), None, observed_at)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            return TipObservation(None, str(error), observed_at)
