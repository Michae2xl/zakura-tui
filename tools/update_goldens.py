from pathlib import Path

from zakura_tui.demo import demo_snapshot
from zakura_tui.renderer import render
from zakura_tui.terminal import Capabilities, ColorLevel


CASES = (
    ("starting", 40),
    ("syncing", 60),
    ("syncing", 79),
    ("syncing", 80),
    ("ready", 100),
    ("degraded", 140),
)


def main() -> None:
    target = Path("tests/golden")
    target.mkdir(parents=True, exist_ok=True)
    for state, width in CASES:
        frame = render(
            demo_snapshot(state),
            Capabilities(width, 40, unicode=True, color=ColorLevel.NONE),
            network="Mainnet",
            storage_mode="pruned",
            refresh_seconds=2.0,
        )
        (target / f"{state}-{width}.txt").write_text(
            frame + "\n", "utf-8"
        )


if __name__ == "__main__":
    main()
