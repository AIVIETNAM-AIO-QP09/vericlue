"""One local VeriClue server: API, QR/portrait reader and configured AI modules."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8421


def require_memory() -> None:
    """Preserve the demo laptop's 3 GiB startup guard for Large face models."""
    if os.name != "nt" or os.environ.get("SESSION_FACE_MODELS", "").lower() != "true":
        return

    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (f"value{i}", ctypes.c_ulonglong) for i in range(7)
        ]

    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise SystemExit("Không kiểm tra được RAM.")
    if memory.value1 < 3 * 1024**3:
        raise SystemExit("Cần ít nhất 3 GiB RAM trống để mở các mô hình mặt Large.")


def port_active() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1):
            return True
    except OSError:
        return False


def load_profile(runtime: Path) -> None:
    from dotenv import load_dotenv

    config = runtime / ".env"
    if not config.is_file():
        raise SystemExit("Thiếu cấu hình server hiện có; không tự tạo lại DB hoặc khóa.")
    load_dotenv(config, override=True)
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})


def serve(runtime: Path) -> None:
    load_profile(runtime)
    os.chdir(runtime)
    sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "ml/src")]
    import uvicorn
    from alembic import command
    from alembic.config import Config

    from vericlue_api.main import app

    command.upgrade(Config(str(ROOT / "services/api/alembic.ini")), "head")
    state = app.state.vericlue
    if state.settings.identity_card_enabled:
        state.identity_runtime.preload()
    state.initialize()
    if state.orchestrator.failed_modules:
        raise SystemExit("Có mô-đun không nạp được; kiểm log riêng của server.")
    (runtime / "server.pid").write_text(str(os.getpid()), encoding="ascii")
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        uvicorn.run(
            app, host="127.0.0.1", port=PORT, workers=1, access_log=False, proxy_headers=False
        )
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def stop(runtime: Path) -> None:
    """Stop only the PID whose command line matches this script and runtime."""
    path = runtime / "server.pid"
    if not path.is_file():
        raise SystemExit("Không có PID server đã ghi nhận.")
    pid = int(path.read_text(encoding="ascii"))
    if os.name == "nt":
        query = f"Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' | Select-Object CommandLine | ConvertTo-Json -Compress"
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", query],
            capture_output=True,
            encoding="utf-8",
            check=True,
        )
        info = json.loads(result.stdout) if result.stdout.strip() else {}
        line = info.get("CommandLine") or ""
    else:
        proc = Path(f"/proc/{pid}/cmdline")
        line = proc.read_bytes().replace(b"\0", b" ").decode() if proc.exists() else ""
    normalized = line.replace("\\", "/").lower()
    if (
        str(Path(__file__).resolve()).replace("\\", "/").lower() not in normalized
        or str(runtime).replace("\\", "/").lower() not in normalized
    ):
        raise SystemExit("PID không thuộc server này; không dừng tiến trình khác.")
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=True)
    else:
        import signal

        os.kill(pid, signal.SIGTERM)
    print("Đã dừng VeriClue; DB và khóa được giữ nguyên.")


@contextmanager
def startup_lock(runtime: Path):
    """Prevent two clicks from launching two model-loading processes."""
    with (runtime / ".startup.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit("Server đang khởi động; không mở thêm tiến trình.") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def start(runtime: Path) -> None:
    if not runtime.is_dir():
        raise SystemExit("Thiếu thư mục cấu hình server hiện có.")
    with startup_lock(runtime):
        _start(runtime)


def _start(runtime: Path) -> None:
    if port_active():
        raise SystemExit("Cổng 8421 đang hoạt động; không mở thêm server.")
    load_profile(runtime)
    require_memory()
    with (
        (runtime / "server.out.log").open("a") as out,
        (runtime / "server.err.log").open("a") as err,
    ):
        args = [
            sys.executable,
            "-u",
            str(Path(__file__).resolve()),
            "serve",
            "--runtime-dir",
            str(runtime),
        ]
        child = subprocess.Popen(
            args,
            cwd=runtime,
            stdout=out,
            stderr=err,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
    deadline = time.monotonic() + 120
    while child.poll() is None and time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=2) as response:
                health = json.load(response)
            if health.get("status") == "ok":
                print("VeriClue sẵn sàng ở cổng 8421; QR và AI chạy trong cùng server.")
                return
        except OSError:
            pass
        time.sleep(1)
    # The Popen handle identifies our own child, even before it writes a PID file.
    if child.poll() is None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, check=True
            )
        else:
            import signal

            os.killpg(child.pid, signal.SIGTERM)
        child.wait(timeout=15)
    raise SystemExit("Server chưa sẵn sàng; kiểm log riêng, không chạy thêm bản khác.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "status", "serve"))
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / "tmp/vericlue-server")
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    if args.action == "status":
        print(json.dumps({"port": PORT, "listening": port_active()}))
    else:
        {"start": start, "stop": stop, "serve": serve}[args.action](runtime)


if __name__ == "__main__":
    main()
