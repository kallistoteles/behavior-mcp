"""The shared worker boundary retains bounded pipe collection and process limits."""

import importlib
import importlib.util
import sys

import pytest

from behavior_mcp.schemas import OperationError


def worker():
    assert importlib.util.find_spec("behavior_mcp.proof_worker"), (
        "Shared bounded worker boundary is absent"
    )
    return importlib.import_module("behavior_mcp.proof_worker")


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_both_streams_are_bounded(stream):
    source = f'import sys; sys.{stream}.write("x"*9000000); sys.{stream}.flush()'
    with pytest.raises(OperationError) as caught:
        worker().run_bounded([sys.executable, "-c", source], {}, timeout=5)
    assert "OUTPUT" in caught.value.code


def test_deadline():
    with pytest.raises(OperationError) as caught:
        worker().run_bounded(
            [sys.executable, "-c", "import time;time.sleep(10)"], {}, timeout=0.1
        )
    assert "TIMEOUT" in caught.value.code


@pytest.mark.parametrize(
    "source",
    [
        "value=bytearray(8*1024**3)",
        "import resource;resource.setrlimit(resource.RLIMIT_CPU,(1,1))\nwhile True: pass",
    ],
)
def test_resource_exhaustion_is_not_success(source):
    with pytest.raises(OperationError) as error:
        worker().run_bounded([sys.executable, "-c", source], {}, timeout=5)
    assert error.value.code == "WORKER_FAILED"


def test_file_limit(tmp_path):
    target = tmp_path / "bounded-worker-output"
    source = (
        f'with open({str(target)!r},"wb") as stream: stream.write(b"x"*(20*1024**2))'
    )
    with pytest.raises(OperationError):
        worker().run_bounded([sys.executable, "-c", source], {}, timeout=5)
    assert target.stat().st_size <= 16 * 1024**2


def test_cancellation_kills_and_reaps_the_worker(monkeypatch):
    import subprocess
    import threading
    import time

    runner = worker()
    processes = []
    original = subprocess.Popen

    def tracked(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", tracked)
    cancelled = threading.Event()
    timer = threading.Timer(0.1, cancelled.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(OperationError) as caught:
            runner.run_bounded(
                [sys.executable, "-c", "import time;time.sleep(10)"],
                {},
                timeout=5,
                cancellation=cancelled,
            )
        assert caught.value.code == "WORKER_CANCELLED"
        assert time.monotonic() - started < 2
        assert processes and processes[0].poll() is not None
    finally:
        timer.join()


async def test_mcp_cancellation_reaches_the_worker(trusted_setup, monkeypatch):
    import subprocess
    import time

    import anyio

    from behavior_mcp.server import Application

    runner = worker()
    processes = []
    original = subprocess.Popen

    def tracked(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", tracked)
    root, context, _, _ = trusted_setup
    app = Application(root, context, "local-delegation")

    def execute(*_):
        runner.run_bounded(
            [sys.executable, "-c", "import time;time.sleep(10)"], {}, timeout=5
        )

    monkeypatch.setattr(app, "execute", execute)
    with anyio.move_on_after(0.2) as scope:
        await app.call_tool("models_list", {})
    assert scope.cancel_called
    deadline = time.monotonic() + 2
    while processes and processes[0].poll() is None and time.monotonic() < deadline:
        await anyio.sleep(0.01)
    assert processes and processes[0].poll() is not None
