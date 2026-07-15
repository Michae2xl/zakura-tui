import io
import os
import pty
import select
import signal
import subprocess
import time
from pathlib import Path

from zakura_tui.terminal import TerminalSession


def test_session_enters_draws_once_and_restores_on_error() -> None:
    stream = io.StringIO()
    try:
        with TerminalSession(stream) as session:
            session.draw("frame")
            session.draw("frame")
            raise RuntimeError("test")
    except RuntimeError:
        pass
    output = stream.getvalue()
    assert output.startswith(TerminalSession.ENTER)
    assert output.count("frame") == 1
    assert output.endswith(TerminalSession.EXIT)


def read_pty(master: int, timeout: float) -> bytes:
    output = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select(
            [master], [], [], max(0.0, deadline - time.monotonic())
        )
        if not ready:
            break
        try:
            chunk = os.read(master, 65_536)
        except OSError:
            break
        if not chunk:
            break
        output.extend(chunk)
    return bytes(output)


def test_demo_restores_terminal_after_sigint() -> None:
    master, slave = pty.openpty()
    command = [
        str(Path(".venv/bin/zakura-status").resolve()),
        "--demo",
        "ready",
        "--no-color",
    ]
    process = subprocess.Popen(
        command,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
    )
    os.close(slave)
    try:
        time.sleep(0.3)
        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=3) == 0
        output = read_pty(master, timeout=0.5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        os.close(master)
    assert TerminalSession.ENTER.encode() in output
    assert TerminalSession.EXIT.encode() in output
