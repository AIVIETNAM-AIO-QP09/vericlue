"""Opt-in child runtime for NES2Net; bounded RAM pipes, cancellation and watchdog.

Uses stdlib Popen with argument lists, binary pipes and CREATE_NO_WINDOW on
Windows. One bounded exchange at a time; stderr DEVNULL cannot fill a pipe.
No executable/model download, shell, network, microphone or audio files.
"""

from __future__ import annotations

import json
import math
import os
import queue
import subprocess
import threading
import uuid
from contextlib import suppress
from pathlib import Path
from time import perf_counter

import numpy as np

from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval.voice_wire import MAX_REPLY, PROTOCOL, encode_request
from vericlue_ml.voice.nes2net import VERSION


def unavailable(code: str = "E_INTERNAL", *, model_version: str = VERSION) -> dict:
    """A failed worker can never produce an accepted voice decision."""
    return {
        "worker_available": False,
        "calibrated": False,
        "frontend_parity_verified": False,
        "result": ModuleResult(
            module="voice_spoof",
            model_version=model_version,
            status="error",
            gate="unclear",
            error_code=code,
            latency_ms=0,
        ).to_contract(),
    }


def validate_reply(
    raw: bytes,
    request_id: str,
    checksum: str,
    *,
    expected_version: str = VERSION,
    sample_count: int | None = None,
) -> dict:
    """Require the current take and the raw-only NES2Net contract, even after restart."""
    if len(raw) > MAX_REPLY or not raw.endswith(b"\n"):
        raise ValueError("Invalid reply bounds")
    body = json.loads(raw)
    if (
        not isinstance(body, dict)
        or body.get("protocol") != PROTOCOL
        or body.get("request_id") != request_id
        or body.get("pcm_float32_sha256") != checksum
        or body.get("model_version") != expected_version
        or body.get("frontend_parity_verified") is not False
        or body.get("calibrated") is not False
    ):
        raise ValueError("Unexpected worker/take")
    result = ModuleResult.model_validate(body["result"])
    if (
        result.module != "voice_spoof"
        or result.model_version != expected_version
        or result.gate != "unclear"
        or result.prob_attack is not None
        or result.status not in {"degraded", "error", "not_applicable"}
        or not math.isfinite(result.latency_ms)
        or (result.score is not None and not math.isfinite(result.score))
        or (result.status != "degraded" and result.score is not None)
    ):
        raise ValueError("Worker is not a raw diagnostic")
    from vericlue_ml.voice.nes2net_timeline import VERSION as TIMELINE_VERSION
    from vericlue_ml.voice.nes2net_timeline import validate_timeline

    if expected_version == TIMELINE_VERSION:
        if type(sample_count) is not int or body.get("received_samples") != sample_count:
            raise ValueError("Wrong timeline length")
        validate_timeline(result, sample_count)
    body["result"] = result.to_contract()
    body["worker_available"] = True
    return body


class Nes2NetClient:
    """Lazy worker, serialized requests; UI cancellation only signals/terminates, never waits."""

    def __init__(
        self,
        python: Path,
        models_dir: Path,
        *,
        timeout: float = 180,
        whole_utterance: bool = False,
    ) -> None:
        from vericlue_ml.voice.nes2net_timeline import VERSION as TIMELINE_VERSION

        if type(whole_utterance) is not bool:
            raise ValueError("Expected explicit timeline mode")
        self.whole_utterance = whole_utterance
        self.version = TIMELINE_VERSION if whole_utterance else VERSION
        self.python, self.models_dir = python.resolve(), models_dir.resolve()
        if not self.python.is_file() or self.python.suffix.lower() in {".bat", ".cmd"}:
            raise ValueError("Select a local Python executable, not a batch file")
        if not math.isfinite(timeout) or not 0 < timeout <= 600:
            raise ValueError("Invalid worker timeout")
        self.timeout = timeout
        self._process = None
        self._state_lock = threading.Lock()
        self._request_lock = threading.Lock()
        self._closed = False
        self._epoch = 0

    def _start(self):
        # Dispose an already-exited worker before replacing it, including pipe handles.
        with self._state_lock:
            exited = self._process is not None and self._process.poll() is not None
        if exited:
            self.cancel()
        with self._state_lock:
            if self._closed:
                raise RuntimeError("Worker client closed")
            if self._process is not None:
                return self._process
            epoch = self._epoch
        repo = Path(__file__).resolve().parents[4]
        env = {
            **os.environ,
            "PYTHONPATH": str(repo / "ml/src"),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
        # Process creation can be slow on some OSes; never hold the UI's state lock here.
        spawned = queue.Queue(maxsize=1)

        def launch():
            process = None
            try:
                process = subprocess.Popen(
                    [
                        str(self.python),
                        "-u",
                        "-X",
                        "utf8",
                        "-m",
                        "vericlue_ml.eval.nes2net_worker",
                        "--models-dir",
                        str(self.models_dir),
                        *(["--whole-utterance"] if self.whole_utterance else []),
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    cwd=repo,
                    shell=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                with self._state_lock:
                    if not self._closed and epoch == self._epoch:
                        self._process = process
                        spawned.put_nowait(process)
                        return
            except Exception:
                pass
            self._dispose(process)
            spawned.put_nowait(None)

        # Keep cleanup alive if the window closes during OS process creation.
        threading.Thread(target=launch, daemon=False).start()
        process = spawned.get()
        if process is None:
            raise RuntimeError("Worker unavailable/cancelled while spawning")
        return process

    def cancel(self) -> None:
        """Dispose only this client's worker; pipe close/reaping runs outside the UI thread."""
        with self._state_lock:
            self._epoch += 1
            process, self._process = self._process, None
        self._dispose(process)

    @staticmethod
    def _dispose(process) -> None:
        if process is None:
            return

        def reap():
            if os.name == "nt" and process.poll() is None:
                # Windows venv launchers may have a real Python child. Kill only
                # the tree rooted at our own Popen PID, not just the launcher.
                taskkill = Path(os.environ["SYSTEMROOT"]) / "System32/taskkill.exe"
                with suppress(OSError, subprocess.TimeoutExpired):
                    subprocess.run(
                        [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        timeout=5,
                        check=False,
                        shell=False,
                    )
            with suppress(OSError):
                process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            finally:
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        stream.close()

        threading.Thread(target=reap, daemon=False).start()

    def close(self) -> None:
        with self._state_lock:
            self._closed = True
        self.cancel()

    def predict_samples(self, samples: np.ndarray, *, cancelled: threading.Event) -> dict:
        """Bound request/response; timeout or cancellation kills the child and discards its result."""
        with self._request_lock:
            started = perf_counter()
            request_id = checksum = None

            def failure(code="E_INTERNAL"):
                body = unavailable(code, model_version=self.version)
                body.update(
                    request_id=request_id,
                    pcm_float32_sha256=checksum,
                    round_trip_ms=(perf_counter() - started) * 1000,
                )
                return body

            try:
                if cancelled.is_set():
                    return failure()
                request_id = uuid.uuid4().hex
                frame, checksum = encode_request(samples, request_id)
                process = self._start()
                replies = queue.Queue(maxsize=1)

                def exchange():
                    try:
                        process.stdin.write(frame)
                        process.stdin.flush()
                        value = process.stdout.readline(MAX_REPLY + 1)
                        replies.put_nowait((value, None))
                    except Exception:
                        replies.put_nowait((None, True))

                threading.Thread(target=exchange, daemon=True).start()
                deadline = started + self.timeout
                while True:
                    if cancelled.is_set() or self._closed:
                        self.cancel()
                        return failure()
                    remaining = deadline - perf_counter()
                    if remaining <= 0:
                        self.cancel()
                        return failure("E_TIMEOUT")
                    try:
                        raw, error = replies.get(timeout=min(0.05, remaining))
                        break
                    except queue.Empty:
                        continue
                if error or cancelled.is_set() or self._closed:
                    raise ValueError("Worker stopped")
                payload = validate_reply(
                    raw,
                    request_id,
                    checksum,
                    expected_version=self.version,
                    sample_count=len(samples),
                )
                payload["round_trip_ms"] = (perf_counter() - started) * 1000
                return payload
            except Exception:
                self.cancel()
                return failure()
