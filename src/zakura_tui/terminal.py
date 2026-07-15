from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from enum import IntEnum
from typing import Mapping, TextIO


class ColorLevel(IntEnum):
    NONE = 0
    ANSI16 = 1
    ANSI256 = 2
    TRUECOLOR = 3


@dataclass(frozen=True)
class Capabilities:
    columns: int
    lines: int
    unicode: bool
    color: ColorLevel


def detect_capabilities(
    stream: TextIO,
    *,
    environ: Mapping[str, str] | None = None,
    size: tuple[int, int] | None = None,
) -> Capabilities:
    env = os.environ if environ is None else environ
    terminal_size = size or shutil.get_terminal_size((80, 24))
    encoding = (getattr(stream, "encoding", None) or "utf-8").lower()
    unicode = "utf" in encoding and env.get("TERM") != "dumb"
    is_tty = bool(getattr(stream, "isatty", lambda: False)())
    if "NO_COLOR" in env or env.get("TERM") == "dumb" or not is_tty:
        color = ColorLevel.NONE
    elif env.get("COLORTERM", "").lower() in {"truecolor", "24bit"}:
        color = ColorLevel.TRUECOLOR
    elif "256color" in env.get("TERM", ""):
        color = ColorLevel.ANSI256
    else:
        color = ColorLevel.ANSI16
    return Capabilities(terminal_size[0], terminal_size[1], unicode, color)


class TerminalSession:
    ENTER = "\x1b[?1049h\x1b[?25l"
    EXIT = "\x1b[0m\x1b[?25h\x1b[?1049l"

    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self._last_frame: str | None = None

    def __enter__(self) -> TerminalSession:
        self.stream.write(self.ENTER)
        self.stream.flush()
        return self

    def draw(self, frame: str) -> None:
        if frame == self._last_frame:
            return
        self.stream.write("\x1b[H\x1b[2J" + frame)
        self.stream.flush()
        self._last_frame = frame

    def __exit__(self, *exc_info: object) -> None:
        self.stream.write(self.EXIT)
        self.stream.flush()
