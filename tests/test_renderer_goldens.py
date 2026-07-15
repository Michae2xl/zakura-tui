from pathlib import Path

import pytest

from tools.update_goldens import CASES
from zakura_tui.demo import demo_snapshot
from zakura_tui.renderer import render
from zakura_tui.terminal import Capabilities, ColorLevel


@pytest.mark.parametrize(("state", "width"), CASES)
def test_renderer_matches_reviewed_golden(state: str, width: int) -> None:
    actual = render(
        demo_snapshot(state),
        Capabilities(width, 40, unicode=True, color=ColorLevel.NONE),
        network="Mainnet",
        storage_mode="pruned",
        refresh_seconds=2.0,
    )
    expected = Path(f"tests/golden/{state}-{width}.txt").read_text(
        "utf-8"
    ).rstrip("\n")
    assert actual == expected
