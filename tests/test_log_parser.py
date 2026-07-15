from pathlib import Path

from zakura_tui.log_parser import (
    IncrementalLogReader,
    merge_log_updates,
    parse_log_line,
)
from zakura_tui.model import SyncObservation


def test_parses_real_progress_line() -> None:
    line = (
        Path("tests/fixtures/zakurad-progress.log")
        .read_text("utf-8")
        .splitlines()[1]
    )
    update = parse_log_line(line)
    assert update is not None
    assert update.sync_percent == 99.824
    assert update.current_height == 3_413_389
    assert update.remaining_blocks == 5_928
    assert update.network_upgrade == "Nu6_2"


def test_parses_verified_block_activity() -> None:
    line = (
        Path("tests/fixtures/zakurad-progress.log")
        .read_text("utf-8")
        .splitlines()[0]
    )
    update = parse_log_line(line)
    assert update is not None
    assert update.current_height == 3_413_389
    assert update.latest_activity == "17:01:15 block 3,413,389 verified"


def test_merge_preserves_previous_values() -> None:
    current = SyncObservation(sync_percent=50.0, network_upgrade="Nu6")
    block = parse_log_line(
        "2026-07-15T17:01:15Z downloaded and verified gossiped block "
        "height=Height(12)"
    )
    merged = merge_log_updates(current, [block], observed_at=10.0)
    assert merged.sync_percent == 50.0
    assert merged.current_height == 12
    assert merged.observed_at == 10.0


def test_reader_holds_partial_line_until_newline(tmp_path: Path) -> None:
    log = tmp_path / "zakurad.log"
    log.write_text("first", encoding="utf-8")
    reader = IncrementalLogReader(log)
    assert reader.poll() == []
    with log.open("a", encoding="utf-8") as handle:
        handle.write(" line\n")
    assert reader.poll() == ["first line"]


def test_reader_recovers_from_truncation(tmp_path: Path) -> None:
    log = tmp_path / "zakurad.log"
    log.write_text("old content\n", encoding="utf-8")
    reader = IncrementalLogReader(log)
    assert reader.poll() == ["old content"]
    log.write_text("new\n", encoding="utf-8")
    assert reader.poll() == ["new"]


def test_reader_recovers_from_rotation(tmp_path: Path) -> None:
    log = tmp_path / "zakurad.log"
    rotated = tmp_path / "zakurad.log.1"
    log.write_text("before rotation\n", encoding="utf-8")
    reader = IncrementalLogReader(log)
    assert reader.poll() == ["before rotation"]
    log.rename(rotated)
    log.write_text("after rotation\n", encoding="utf-8")
    assert reader.poll() == ["after rotation"]


def test_reader_bounds_the_initial_history(tmp_path: Path) -> None:
    log = tmp_path / "zakurad.log"
    log.write_text("stale\n" * 100 + "latest\n", encoding="utf-8")
    reader = IncrementalLogReader(log, initial_bytes=32)
    lines = reader.poll()
    assert lines[-1] == "latest"
    assert len(lines) < 10
