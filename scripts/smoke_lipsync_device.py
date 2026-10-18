"""Manual isolated API/device smoke; diagnostics are not accuracy or latency benchmarks."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def gpu_memory() -> dict:
    """Total GPU usage includes other processes; Torch counters describe this process."""
    result = {}
    try:
        query = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        result["total_gpu_mib_including_other_processes"] = [
            dict(zip(("index", "used", "total"), map(int, line.split(",")), strict=True))
            for line in query.stdout.strip().splitlines()
        ]
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result["nvidia_smi_error"] = type(exc).__name__
    try:
        import torch

        result["torch_process_bytes"] = [
            {
                "index": i,
                "allocated": torch.cuda.memory_allocated(i),
                "reserved": torch.cuda.memory_reserved(i),
            }
            for i in range(torch.cuda.device_count())
        ]
    except Exception as exc:  # Diagnostic availability must not erase completed checkpoints.
        result["torch_error"] = type(exc).__name__
    return result


def lipsync_state(engine) -> dict:
    """Read device/load snapshots without blocking on the lipsync inference lock."""
    from vericlue_ml.common.result import Module

    detector = engine._detectors.get(Module.LIPSYNC)
    aligner = getattr(detector, "_aligner", None)
    backend = getattr(detector, "_backend", None)
    ctc = getattr(aligner, "_backend", None)
    running, queued = ["startup_or_busy"], None
    if engine._lifecycle.acquire(blocking=False):
        try:
            running = sorted(str(module) for module in engine._running)
            queued = len(engine._queues[Module.LIPSYNC])
        finally:
            engine._lifecycle.release()
    return {
        "requested_device": getattr(detector, "_requested_device", None),
        "detector_device": getattr(detector, "_device", None),
        "loaded": getattr(detector, "_loaded", False),
        "backend_device": getattr(backend, "device", None),
        "backend_loaded": getattr(backend, "model", None) is not None,
        "aligner_device": getattr(ctc, "device", None),
        "aligner_loaded": getattr(ctc, "model", None) is not None,
        "running_modules": running,
        "lipsync_queued": queued,
        "worker_pending": queued is None or str(Module.LIPSYNC) in running or queued > 0,
    }


def summary(result) -> dict:
    """Keep module diagnostics without transcript or media evidence."""
    return {
        "status": result.status,
        "error_code": result.error_code,
        "latency_ms": result.latency_ms,
        "model_version": result.model_version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("models-dir", "image", "video", "audio", "prompt-file", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--port", type=int, default=8200)
    args = parser.parse_args()
    if args.port == 8000 or not 1 <= args.port <= 65535:
        parser.error("Use a private non-demo port; port 8000 is forbidden")
    # Own the socket before creating an app; never connect to an existing API by mistake.
    listener = socket.socket()
    listener.bind(("127.0.0.1", args.port))
    listener.listen(128)
    (ROOT / "tmp").mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="lipsync-device-", dir=ROOT / "tmp"))
    os.environ.update(
        ROUTER_PROFILE="mvp",
        USE_MOCK_MODELS="false",
        DEVICE="cuda",
        LIPSYNC_DEVICE="cpu",
        MODELS_DIR=str(args.models_dir.resolve()),
        MEDIA_DIR=str(work / "media"),
        DATABASE_URL="sqlite:///" + (work / "smoke.db").as_posix(),
        DATABASE_HOST="",
        DETECTOR_TIMEOUT_SECONDS="4",
        INFERENCE_BUDGET_SECONDS="4.8",
    )
    import httpx
    import uvicorn

    from vericlue_api.core.config import get_settings
    from vericlue_api.db.models import Base
    from vericlue_api.main import create_app
    from vericlue_ml.common.result import Module

    get_settings.cache_clear()
    app = create_app()
    Base.metadata.create_all(app.state.vericlue.database.engine)
    engine = app.state.vericlue.orchestrator
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    report = {
        "purpose": "manual_device_smoke_not_evaluation",
        "port": args.port,
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "requested": {"device": "cuda", "lipsync_device": "cpu", "detector_timeout_seconds": 4},
        "sessions": [],
        "checkpoints": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save(phase):
        checkpoint = {"phase": phase, "gpu": gpu_memory(), "lipsync": lipsync_state(engine)}
        report["checkpoints"].append(checkpoint)
        staged = args.output.with_name(args.output.name + ".partial")
        staged.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staged.replace(args.output)
        print(json.dumps(checkpoint, ensure_ascii=True), flush=True)

    try:
        save("before_preload")
        thread.start()
        deadline = time.monotonic() + 180
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Private smoke API failed to start within 180 seconds")
            time.sleep(1)
        report["failed_preload_modules"] = engine.failed_modules
        report["model_versions"] = {str(m): d.version for m, d in engine._detectors.items()}
        save("after_preload")
        prompt = args.prompt_file.read_text(encoding="utf-8")
        with httpx.Client(base_url=f"http://127.0.0.1:{args.port}", timeout=20) as client:
            for index in range(1, 4):
                created = client.post("/v1/sessions")
                created.raise_for_status()
                session = created.json()
                sid = session["session_id"]
                headers = {"Authorization": "Bearer " + session["token"]}
                with args.image.open("rb") as image, args.video.open("rb") as video:
                    uploaded = client.post(
                        f"/v1/sessions/{sid}/media",
                        headers=headers,
                        files={
                            "image": (args.image.name, image),
                            "video": (args.video.name, video),
                        },
                    )
                uploaded.raise_for_status()
                finalized = client.post(f"/v1/sessions/{sid}/finalize", headers=headers)
                finalized.raise_for_status()
                with app.state.vericlue.transaction() as state:
                    results = state.sessions.get(sid).results
                    face = {
                        str(m): summary(results[m]) if m in results else {"status": "missing"}
                        for m in (Module.QUALITY, Module.FACE_PAD, Module.FACE_DEEPFAKE)
                    }
                record = {
                    "index": index,
                    "finalize_status": finalized.json()["status"],
                    "face_modules": face,
                }
                report["sessions"].append(record)
                save(f"after_session_{index}")
                diagnostic = engine.run(
                    [Module.LIPSYNC],
                    session_id=None,
                    scenario="genuine",
                    video=args.video,
                    audio=args.audio,
                    extra_metadata={"prompt": prompt},
                )
                record["direct_lipsync_diagnostic_not_voice_gate"] = summary(
                    diagnostic[Module.LIPSYNC]
                )
                save(f"after_direct_lipsync_diagnostic_{index}")
        start = time.monotonic()
        while lipsync_state(engine)["worker_pending"] and time.monotonic() - start < 120:
            time.sleep(1)
        report["worker_wait_seconds"] = time.monotonic() - start
        report["lipsync_worker_finished_within_120s"] = not lipsync_state(engine)["worker_pending"]
        save("after_lipsync_worker_wait")
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        save("failed")
        raise
    finally:
        server.should_exit = True
        if thread.ident is not None:
            thread.join(timeout=10)
        listener.close()
        report["own_server_stopped"] = not thread.is_alive()
        save("stopped_own_server")


if __name__ == "__main__":
    main()
