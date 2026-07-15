from __future__ import annotations

import threading
import time
from dataclasses import replace
from queue import Empty, SimpleQueue
from typing import Callable, Protocol

from .config import Config
from .log_parser import IncrementalLogReader, merge_log_updates, parse_log_line
from .model import NodeSnapshot, SyncObservation, TipObservation, resolve_snapshot
from .probes import HealthProbe, ServiceProbe, TipHeightProbe


class Probe(Protocol):
    def poll(self): ...


class LogReader(Protocol):
    def poll(self) -> list[str]: ...


class NodeMonitor:
    def __init__(
        self,
        config: Config,
        *,
        service_probe: Probe | None = None,
        health_probe: Probe | None = None,
        tip_probe: Probe | None = None,
        log_reader: LogReader | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self.clock = clock
        self.started_at = clock()
        self.service_probe = service_probe or ServiceProbe(config.service_name)
        self.health_probe = health_probe or HealthProbe(
            config.health_url, timeout=1.0
        )
        self.tip_probe = tip_probe or TipHeightProbe(
            zakurad_path=config.zakurad_path,
            config_path=config.zakura_config_path,
            network=config.network,
            timeout=config.tip_timeout_seconds,
        )
        self.log_reader = log_reader or IncrementalLogReader(config.log_path)
        self.sync = SyncObservation()
        self._tip_results: SimpleQueue[TipObservation | Exception] = SimpleQueue()
        self._tip_thread: threading.Thread | None = None
        self._closed = threading.Event()
        self._last_tip_started = float("-inf")
        self._tip_diagnostic: str | None = None

    def _run_tip(self) -> None:
        try:
            result: TipObservation | Exception = self.tip_probe.poll()
        except Exception as error:
            result = error
        if not self._closed.is_set():
            self._tip_results.put(result)

    def _consume_tip(self) -> None:
        try:
            result = self._tip_results.get_nowait()
        except Empty:
            return
        self._tip_thread = None
        if self.sync.current_height is not None:
            self._tip_diagnostic = None
            return
        if isinstance(result, Exception):
            self._tip_diagnostic = (
                f"TIP FALLBACK FAILED: {self.config.zakurad_path}: {result}"
            )
            return
        observation = result
        if observation.error:
            self._tip_diagnostic = (
                "TIP FALLBACK FAILED: "
                f"{self.config.zakurad_path}: {observation.error}"
            )
        elif observation.height is not None and self.sync.current_height is None:
            self._tip_diagnostic = None
            self.sync = replace(
                self.sync,
                current_height=observation.height,
                observed_at=observation.observed_at,
            )

    def _schedule_tip(self, now: float) -> None:
        if (
            self._closed.is_set()
            or self.sync.current_height is not None
            or self._tip_thread is not None
        ):
            return
        if now - self._last_tip_started < 60.0:
            return
        self._last_tip_started = now
        self._tip_thread = threading.Thread(
            target=self._run_tip,
            name="zakura-tip",
            daemon=True,
        )
        self._tip_thread.start()

    def poll(self) -> NodeSnapshot:
        now = self.clock()
        service = self.service_probe.poll()
        health = self.health_probe.poll()
        diagnostics: list[str] = []
        try:
            updates = [parse_log_line(line) for line in self.log_reader.poll()]
        except FileNotFoundError:
            diagnostics.append(f"WAITING FOR LOG: {self.config.log_path}")
            updates = []
        except PermissionError:
            diagnostics.append(
                f"PERMISSION DENIED: {self.config.log_path} "
                "(read permission required)"
            )
            updates = []
        except OSError as error:
            diagnostics.append(
                f"LOG UNAVAILABLE: {self.config.log_path}: {error}"
            )
            updates = []
        self.sync = merge_log_updates(self.sync, updates, observed_at=now)
        self._consume_tip()
        self._schedule_tip(now)
        if self._tip_diagnostic:
            diagnostics.append(self._tip_diagnostic)
        return resolve_snapshot(
            service=service,
            health=health,
            sync=self.sync,
            now=now,
            started_at=self.started_at,
            startup_grace_seconds=self.config.startup_grace_seconds,
            health_stale_seconds=self.config.health_stale_seconds,
            diagnostics=tuple(diagnostics),
        )

    def close(self) -> None:
        self._closed.set()
