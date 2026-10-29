"""A single server entry point must not start duplicates or kill unrelated processes."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

_spec = spec_from_file_location("vericlue_server_cli", Path(__file__).parents[1] / "server.py")
server = module_from_spec(_spec)
_spec.loader.exec_module(server)


def test_startup_is_exclusive_and_releases_after_error(tmp_path):
    with pytest.raises(RuntimeError), server.startup_lock(tmp_path):
        with pytest.raises(SystemExit, match="khởi động"), server.startup_lock(tmp_path):
            pytest.fail("second start must not enter")
        raise RuntimeError("simulated startup failure")
    with server.startup_lock(tmp_path):
        pass


def test_active_port_cannot_launch_another_server(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "port_active", lambda: True)
    with pytest.raises(SystemExit, match="8421"):
        server.start(tmp_path)


def test_stop_refuses_a_reused_pid(tmp_path, monkeypatch):
    (tmp_path / "server.pid").write_text("12345", encoding="ascii")
    calls = []
    if server.os.name == "nt":
        from types import SimpleNamespace

        def run(args, **kwargs):
            calls.append(args[0])
            return SimpleNamespace(stdout='{"CommandLine":"another-program.exe"}')

        monkeypatch.setattr(server.subprocess, "run", run)
    else:
        original = Path.exists
        monkeypatch.setattr(
            Path, "exists", lambda p: False if str(p).startswith("/proc/") else original(p)
        )
        monkeypatch.setattr(server.os, "kill", lambda *args: calls.append("kill"))
    with pytest.raises(SystemExit, match="PID"):
        server.stop(tmp_path)
    assert "taskkill" not in calls and "kill" not in calls
