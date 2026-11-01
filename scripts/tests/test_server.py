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


def test_start_can_wait_for_configured_real_model_warmup(tmp_path, monkeypatch):
    import io
    from types import SimpleNamespace

    clock = [0.0]
    stopped = []
    child = SimpleNamespace(poll=lambda: None, pid=54321, wait=lambda **_: None)
    monkeypatch.setenv("VERICLUE_STARTUP_TIMEOUT_SECONDS", "180")
    monkeypatch.setattr(server, "port_active", lambda: False)
    monkeypatch.setattr(server, "load_profile", lambda _: None)
    monkeypatch.setattr(server, "require_memory", lambda: None)
    monkeypatch.setattr(server.subprocess, "Popen", lambda *a, **k: child)
    monkeypatch.setattr(server.subprocess, "run", lambda *a, **k: stopped.append(True))
    monkeypatch.setattr(server.os, "killpg", lambda *a: stopped.append(True), raising=False)
    monkeypatch.setattr(server.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(server.time, "sleep", lambda _: clock.__setitem__(0, clock[0] + 30))

    def health(*args, **kwargs):
        if clock[0] < 150:
            raise OSError("Model warmup still running")
        return io.StringIO('{"status":"ok"}')

    monkeypatch.setattr(server.urllib.request, "urlopen", health)
    server.start(tmp_path)
    assert clock[0] == 150
    assert not stopped


@pytest.mark.parametrize("timeout", ["invalid", "nan", "inf", "-1", "0", "29", "601"])
def test_bad_startup_timeout_never_spawns_a_process(tmp_path, monkeypatch, timeout):
    monkeypatch.setenv("VERICLUE_STARTUP_TIMEOUT_SECONDS", timeout)
    monkeypatch.setattr(server, "port_active", lambda: False)
    monkeypatch.setattr(server, "load_profile", lambda _: None)
    monkeypatch.setattr(server, "require_memory", lambda: None)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid startup configuration must be rejected before spawn")

    monkeypatch.setattr(server.subprocess, "Popen", forbidden)
    with pytest.raises(SystemExit, match="STARTUP_TIMEOUT"):
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
