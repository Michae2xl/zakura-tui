from __future__ import annotations

import re
from itertools import groupby

from .generated_brand import (
    ASCII_COMPACT,
    COMPACT_COLORS,
    COMPACT_GLYPHS,
    FULL_COLORS,
    FULL_GLYPHS,
)
from .model import NodeSnapshot, NodeState
from .terminal import Capabilities, ColorLevel


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
UNTRUSTED_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
PINK = {
    ColorLevel.ANSI16: "95",
    ColorLevel.ANSI256: "38;5;205",
    ColorLevel.TRUECOLOR: "38;2;253;103;152",
}
GREEN = {
    ColorLevel.ANSI16: "92",
    ColorLevel.ANSI256: "38;5;84",
    ColorLevel.TRUECOLOR: "38;2;88;223;145",
}
AMBER = {
    ColorLevel.ANSI16: "93",
    ColorLevel.ANSI256: "38;5;220",
    ColorLevel.TRUECOLOR: "38;2;255;209;102",
}


def safe_text(text: str) -> str:
    return CONTROL_RE.sub(" ", UNTRUSTED_ANSI_RE.sub("", text))


def paint(
    text: str, palette: dict[ColorLevel, str], caps: Capabilities
) -> str:
    code = palette.get(caps.color)
    return f"\x1b[{code}m{text}\x1b[0m" if code else text


def render_art(
    glyphs: tuple[str, ...], colors: tuple[str, ...], caps: Capabilities
) -> list[str]:
    rendered: list[str] = []
    for glyph_line, color_line in zip(glyphs, colors, strict=True):
        pieces: list[str] = []
        start = 0
        for color, group in groupby(color_line):
            width = len(list(group))
            text = glyph_line[start : start + width]
            pieces.append(paint(text, PINK, caps) if color == "p" else text)
            start += width
        rendered.append("".join(pieces))
    return rendered


def progress_bar(percent: float | None, width: int) -> str:
    value = max(0.0, min(100.0, percent or 0.0))
    filled = round(width * value / 100.0)
    return "█" * filled + "░" * (width - filled)


def truncate_ansi(text: str, width: int) -> str:
    output: list[str] = []
    visible = 0
    position = 0
    for match in ANSI_RE.finditer(text):
        plain = text[position : match.start()]
        take = max(0, width - visible)
        output.append(plain[:take])
        visible += min(len(plain), take)
        if visible >= width:
            break
        output.append(match.group())
        position = match.end()
    else:
        output.append(text[position : position + max(0, width - visible)])
    return "".join(output) + ("\x1b[0m" if "\x1b[" in text else "")


def render(
    snapshot: NodeSnapshot,
    caps: Capabilities,
    *,
    network: str,
    storage_mode: str,
    refresh_seconds: float,
) -> str:
    width = max(1, caps.columns)
    if width >= 80 and caps.unicode:
        lines = render_art(FULL_GLYPHS, FULL_COLORS, caps)
    elif width >= 60 and caps.unicode:
        lines = render_art(COMPACT_GLYPHS, COMPACT_COLORS, caps)
    elif width >= 60:
        lines = list(ASCII_COMPACT)
    else:
        lines = ["(*) ZAKURA"]

    sync = snapshot.sync
    height = f"{sync.current_height:,}" if sync.current_height is not None else "--"
    percent = (
        f"{sync.sync_percent:.3f}%" if sync.sync_percent is not None else "--"
    )
    remaining = (
        f"{sync.remaining_blocks:,}" if sync.remaining_blocks is not None else "--"
    )
    upgrade = safe_text(sync.network_upgrade or "--").upper()
    status_palette = (
        GREEN
        if snapshot.state is NodeState.READY
        else (
            AMBER
            if snapshot.state in {NodeState.STARTING, NodeState.SYNCING}
            else PINK
        )
    )
    lines.extend(
        [
            f"{safe_text(network).upper()} / {safe_text(storage_mode).upper()}",
            paint(safe_text(snapshot.status_message), status_palette, caps),
            paint(
                progress_bar(sync.sync_percent, max(10, min(width - 2, 52))),
                status_palette,
                caps,
            ),
        ]
    )
    if width >= 80:
        lines.extend(
            [
                f"HEIGHT  {height:<18} SYNC  {percent}",
                f"LEFT    {remaining:<18} UPGRADE  {upgrade}",
            ]
        )
    else:
        lines.extend(
            [
                f"HEIGHT {height}  SYNC {percent}",
                f"LEFT {remaining}  UPGRADE {upgrade}",
            ]
        )
    health = (
        "ready"
        if snapshot.health and snapshot.health.ready
        else (safe_text(snapshot.health.detail) if snapshot.health else "waiting")
    )
    lines.append(f"service {safe_text(snapshot.service.detail)}  health {health}")
    if sync.latest_activity and width >= 60:
        lines.append(safe_text(sync.latest_activity))
    lines.extend(safe_text(item) for item in snapshot.diagnostics)
    lines.append(f"refresh {refresh_seconds:g}s  Ctrl+C to exit")
    return "\n".join(truncate_ansi(line, width) for line in lines[: caps.lines])
