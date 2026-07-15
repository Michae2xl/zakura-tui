from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

from .model import SyncObservation


PROGRESS_RE = re.compile(
    r"sync_percent=(?P<percent>\d+(?:\.\d+)?)%.*?"
    r"current_height=Height\((?P<height>\d+)\).*?"
    r"network_upgrade=(?P<upgrade>\S+).*?"
    r"remaining_sync_blocks=(?P<remaining>\d+)"
)
BLOCK_RE = re.compile(
    r"downloaded and verified gossiped block height=Height\((?P<height>\d+)\)"
)
TIME_RE = re.compile(r"T(?P<clock>\d{2}:\d{2}:\d{2})(?:\.\d+)?Z")


@dataclass(frozen=True)
class LogUpdate:
    sync_percent: float | None = None
    current_height: int | None = None
    remaining_blocks: int | None = None
    network_upgrade: str | None = None
    latest_activity: str | None = None


def parse_log_line(line: str) -> LogUpdate | None:
    if match := PROGRESS_RE.search(line):
        return LogUpdate(
            sync_percent=float(match.group("percent")),
            current_height=int(match.group("height")),
            remaining_blocks=int(match.group("remaining")),
            network_upgrade=match.group("upgrade"),
        )
    if match := BLOCK_RE.search(line):
        height = int(match.group("height"))
        clock = TIME_RE.search(line)
        prefix = f"{clock.group('clock')} " if clock else ""
        return LogUpdate(
            current_height=height,
            latest_activity=f"{prefix}block {height:,} verified",
        )
    return None


def merge_log_updates(
    current: SyncObservation,
    updates: list[LogUpdate | None],
    *,
    observed_at: float,
) -> SyncObservation:
    merged = current
    for update in updates:
        if update is None:
            continue
        merged = replace(
            merged,
            sync_percent=(
                update.sync_percent
                if update.sync_percent is not None
                else merged.sync_percent
            ),
            current_height=(
                update.current_height
                if update.current_height is not None
                else merged.current_height
            ),
            remaining_blocks=(
                update.remaining_blocks
                if update.remaining_blocks is not None
                else merged.remaining_blocks
            ),
            network_upgrade=(
                update.network_upgrade
                if update.network_upgrade is not None
                else merged.network_upgrade
            ),
            latest_activity=(
                update.latest_activity
                if update.latest_activity is not None
                else merged.latest_activity
            ),
            observed_at=observed_at,
        )
    return merged


class IncrementalLogReader:
    def __init__(self, path: Path, *, initial_bytes: int = 1_048_576) -> None:
        self.path = path
        self._offset = 0
        self._inode: int | None = None
        self._partial = ""
        self._initial_bytes = initial_bytes

    def poll(self) -> list[str]:
        stat = self.path.stat()
        rotated = self._inode is not None and self._inode != stat.st_ino
        truncated = stat.st_size < self._offset
        if rotated or truncated:
            self._offset = 0
            self._partial = ""
        first_read = self._inode is None
        if first_read and stat.st_size > self._initial_bytes:
            self._offset = stat.st_size - self._initial_bytes
        self._inode = stat.st_ino

        with self.path.open("rb") as handle:
            handle.seek(self._offset)
            chunk = handle.read()
            self._offset = handle.tell()

        if not chunk:
            return []
        if first_read and stat.st_size > self._initial_bytes:
            _, separator, chunk = chunk.partition(b"\n")
            if not separator:
                return []
        text = self._partial + chunk.decode("utf-8", "replace")
        lines = text.splitlines(keepends=True)
        self._partial = ""
        if lines and not lines[-1].endswith(("\n", "\r")):
            self._partial = lines.pop()
        return [line.rstrip("\r\n") for line in lines]
