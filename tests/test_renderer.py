import io
import re

import pytest

from zakura_tui.demo import demo_snapshot
from zakura_tui.model import NodeSnapshot
from zakura_tui.renderer import render
from zakura_tui.terminal import Capabilities, ColorLevel, detect_capabilities


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def visible(line: str) -> str:
    return ANSI_RE.sub("", line)


def test_no_color_ready_layout_contains_operator_fields() -> None:
    frame = render(
        demo_snapshot("ready"),
        Capabilities(80, 24, unicode=True, color=ColorLevel.NONE),
        network="Mainnet",
        storage_mode="pruned",
        refresh_seconds=2.0,
    )
    assert "SYNCHRONIZED" in frame
    assert "HEIGHT" in frame
    assert "SYNC" in frame
    assert "NU6_2" in frame
    assert max(map(len, frame.splitlines())) <= 80


def test_all_supported_widths_never_overflow() -> None:
    for width in (10, 20, 39, 40, 60, 79, 80, 100, 140):
        frame = render(
            demo_snapshot("syncing"),
            Capabilities(width, 40, unicode=True, color=ColorLevel.NONE),
            network="Mainnet",
            storage_mode="pruned",
            refresh_seconds=2.0,
        )
        assert all(len(visible(line)) <= width for line in frame.splitlines())


def test_no_color_environment_wins() -> None:
    stream = io.StringIO()
    capabilities = detect_capabilities(
        stream,
        environ={"TERM": "xterm-256color", "NO_COLOR": "1"},
        size=(80, 24),
    )
    assert capabilities.color is ColorLevel.NONE


def test_ascii_fallback_uses_portable_brand() -> None:
    frame = render(
        demo_snapshot("syncing"),
        Capabilities(40, 24, unicode=False, color=ColorLevel.NONE),
        network="Mainnet",
        storage_mode="pruned",
        refresh_seconds=2.0,
    )
    assert "(*) ZAKURA" in frame


@pytest.mark.parametrize(
    ("level", "code"),
    [
        (ColorLevel.ANSI16, "\x1b[95m"),
        (ColorLevel.ANSI256, "\x1b[38;5;205m"),
        (ColorLevel.TRUECOLOR, "\x1b[38;2;253;103;152m"),
    ],
)
def test_color_levels_use_zakura_pink(level: ColorLevel, code: str) -> None:
    frame = render(
        demo_snapshot("ready"),
        Capabilities(80, 24, unicode=True, color=level),
        network="Mainnet",
        storage_mode="pruned",
        refresh_seconds=2.0,
    )
    assert code in frame
    assert any("\u2800" <= character <= "\u28ff" for character in frame)


def test_diagnostics_are_visible() -> None:
    snapshot = demo_snapshot("syncing")
    snapshot = NodeSnapshot(
        snapshot.state,
        snapshot.service,
        snapshot.health,
        snapshot.sync,
        snapshot.status_message,
        ("WAITING FOR LOG: /tmp/zakurad.log",),
    )
    frame = render(
        snapshot,
        Capabilities(80, 24, unicode=True, color=ColorLevel.NONE),
        network="Mainnet",
        storage_mode="pruned",
        refresh_seconds=2.0,
    )
    assert "WAITING FOR LOG: /tmp/zakurad.log" in frame


def test_untrusted_diagnostics_cannot_emit_terminal_controls() -> None:
    snapshot = demo_snapshot("degraded")
    snapshot = NodeSnapshot(
        snapshot.state,
        snapshot.service,
        snapshot.health,
        snapshot.sync,
        snapshot.status_message,
        ("\x1b[2Jbad\nline",),
    )
    frame = render(
        snapshot,
        Capabilities(80, 24, unicode=True, color=ColorLevel.NONE),
        network="Mainnet",
        storage_mode="pruned",
        refresh_seconds=2.0,
    )
    assert "\x1b[2J" not in frame
    assert "bad line" in frame
