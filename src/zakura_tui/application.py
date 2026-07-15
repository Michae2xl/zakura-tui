from __future__ import annotations

import os
import sys
import time
from dataclasses import replace
from typing import Mapping, Protocol, TextIO

from .model import NodeSnapshot
from .renderer import render
from .terminal import Capabilities, ColorLevel, TerminalSession, detect_capabilities


class MonitorLike(Protocol):
    def poll(self) -> NodeSnapshot: ...

    def close(self) -> None: ...


def _capabilities(
    stream: TextIO,
    *,
    environ: Mapping[str, str],
    no_color: bool,
    force_ascii: bool,
) -> Capabilities:
    caps = detect_capabilities(stream, environ=environ)
    if no_color:
        caps = replace(caps, color=ColorLevel.NONE)
    if force_ascii:
        caps = replace(caps, unicode=False)
    return caps


def run_monitor(
    monitor: MonitorLike,
    *,
    network: str,
    storage_mode: str,
    refresh_seconds: float,
    once: bool,
    no_color: bool,
    force_ascii: bool,
    stream: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    output = sys.stdout if stream is None else stream
    env = os.environ if environ is None else environ
    try:
        if not once and not bool(getattr(output, "isatty", lambda: False)()):
            print("interactive mode requires a TTY; use --once", file=sys.stderr)
            return 2
        if once:
            snapshot = monitor.poll()
            caps = _capabilities(
                output,
                environ=env,
                no_color=no_color,
                force_ascii=force_ascii,
            )
            output.write(
                render(
                    snapshot,
                    caps,
                    network=network,
                    storage_mode=storage_mode,
                    refresh_seconds=refresh_seconds,
                )
                + "\n"
            )
            return 0
        try:
            with TerminalSession(output) as terminal:
                while True:
                    snapshot = monitor.poll()
                    caps = _capabilities(
                        output,
                        environ=env,
                        no_color=no_color,
                        force_ascii=force_ascii,
                    )
                    terminal.draw(
                        render(
                            snapshot,
                            caps,
                            network=network,
                            storage_mode=storage_mode,
                            refresh_seconds=refresh_seconds,
                        )
                    )
                    time.sleep(refresh_seconds)
        except KeyboardInterrupt:
            return 0
    finally:
        monitor.close()
