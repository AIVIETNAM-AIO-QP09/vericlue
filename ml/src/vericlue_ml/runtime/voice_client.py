"""One bounded persistent worker per API instance; no shells, uploads or external services."""

import hashlib
import json
import math
import os
import queue
import subprocess
import threading
import uuid
from pathlib import Path
from time import monotonic

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.runtime.voice_wire import (
    KINDS,
    MAX_REPLY,
    MAX_REQUEST,
    PROTOCOL,
    canonical,
    expected_version,
    source_hashes,
)


class VoiceWorkerClient:
    """Serialize exchanges and permanently fail closed after timeout or broken framing."""

    def __init__(
        self, python: Path, models_dir: Path, media_root: Path, *, timeout: float = 30
    ) -> None:
        self.python, self.models_dir, self.media_root = (
            python.resolve(),
            models_dir.resolve(),
            media_root.resolve(),
        )
        self.timeout = timeout
        self._process = None
        self._lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._failed = self._closed = False

    def preload(self) -> None:
        """Validate local runtime configuration; model weights load lazily inside the child."""
        if not self.python.is_file() or self.python.suffix.lower() in {".cmd", ".bat", ".ps1"}:
            raise ValueError("Expected a local Python executable")

    def _line(self, operation, deadline):
        result = queue.Queue(maxsize=1)

        def exchange():
            try:
                result.put((operation(), None))
            except Exception:
                result.put((None, True))

        threading.Thread(target=exchange, daemon=True).start()
        value, error = result.get(timeout=max(0.001, deadline - monotonic()))
        if error:
            raise ValueError("Worker channel failed")
        return value

    def _start(self, deadline):
        if self._closed or self._failed:
            raise RuntimeError("Worker not available")
        if self._process is None:
            self.preload()
            repo = Path(__file__).resolve().parents[4]
            env = {
                **os.environ,
                "PYTHONPATH": str(repo / "ml/src"),
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
            }
            process = subprocess.Popen(
                [
                    str(self.python),
                    "-u",
                    "-X",
                    "utf8",
                    "-m",
                    "vericlue_ml.runtime.voice_worker",
                    "--models-dir",
                    str(self.models_dir),
                    "--media-root",
                    str(self.media_root),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                shell=False,
                cwd=repo,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._state_lock:
                cancelled = self._closed
                if not cancelled:
                    self._process = process
            if cancelled:
                self._dispose(process)
                raise RuntimeError("Closed while spawning worker")
            ready = self._line(lambda: process.stdout.readline(MAX_REPLY + 1), deadline)
            if len(ready) > MAX_REPLY or json.loads(ready) != {"protocol": PROTOCOL, "ready": True}:
                raise ValueError("Invalid worker hello")
        return self._process

    def close(self) -> None:
        """Reap only the process tree started by this client, including Windows venv shims."""
        with self._state_lock:
            self._closed = True
            process, self._process = self._process, None
        self._dispose(process)

    @staticmethod
    def _dispose(process) -> None:
        if process is None:
            return

        def reap():
            try:
                if os.name == "nt" and process.poll() is None:
                    subprocess.run(
                        [
                            str(Path(os.environ["SYSTEMROOT"]) / "System32/taskkill.exe"),
                            "/PID",
                            str(process.pid),
                            "/T",
                            "/F",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                        shell=False,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                elif process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            finally:
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        stream.close()

        threading.Thread(target=reap, daemon=False).start()

    def predict(
        self, kind: str, inp: DetectorInput, *, timeout: float | None = None
    ) -> ModuleResult:
        if kind not in KINDS:
            raise ValueError("Unknown voice worker kind")
        deadline = monotonic() + (self.timeout if timeout is None else min(self.timeout, timeout))
        # Queueing behind another kind is part of this request's budget. A busy
        # worker is not broken, so expiring here must not kill another request.
        if not self._lock.acquire(timeout=max(0.0, deadline - monotonic())):
            return ModuleResult(
                module=KINDS[kind],
                model_version=expected_version(kind),
                status="error",
                gate="unclear",
                error_code="E_TIMEOUT",
                latency_ms=0,
            )
        try:
            return self._predict_locked(kind, inp, deadline)
        finally:
            self._lock.release()

    def _predict_locked(self, kind: str, inp: DetectorInput, deadline: float) -> ModuleResult:
        try:
            sources = source_hashes(inp, self.media_root, kind)
        except (ValueError, OSError):
            # Invalid input must not poison a shared worker for later sessions.
            return ModuleResult(
                module=KINDS[kind],
                model_version=expected_version(kind),
                status="error",
                gate="unclear",
                error_code="E_DECODE",
                latency_ms=0,
            )
        try:
            # Only the voice source fields/metadata are allowed into this private protocol.
            selected = DetectorInput(
                session_id=inp.session_id,
                audio=inp.audio,
                video=inp.video if kind == "lipsync" else None,
                metadata=inp.metadata,
            )
            request = {
                "protocol": PROTOCOL,
                "request_id": uuid.uuid4().hex,
                "kind": kind,
                "input": selected.model_dump(mode="json"),
                "sources": sources,
            }
            raw = canonical(request)
            if len(raw) + 1 > MAX_REQUEST:
                raise ValueError("Request too large")
            process = self._start(deadline)

            def exchange():
                process.stdin.write(raw + b"\n")
                process.stdin.flush()
                return process.stdout.readline(MAX_REPLY + 1)

            response = self._line(exchange, deadline)
            if len(response) > MAX_REPLY or not response.endswith(b"\n"):
                raise ValueError("Reply bounds")
            body = json.loads(response)
            if (
                body.get("protocol") != PROTOCOL
                or body.get("request_id") != request["request_id"]
                or body.get("request_sha256") != hashlib.sha256(raw).hexdigest()
                or body.get("sources") != sources
                or source_hashes(inp, self.media_root, kind) != sources
            ):
                raise ValueError("Stale or changed media")
            result = ModuleResult.model_validate(body["result"])
            if (
                result.module != KINDS[kind]
                or not math.isfinite(result.latency_ms)
                or (result.score is not None and not math.isfinite(result.score))
                or (result.status != "error" and result.model_version != expected_version(kind))
                or (
                    kind != "content"
                    and (
                        result.gate != "unclear"
                        or result.prob_attack is not None
                        or result.status == "ok"
                    )
                )
            ):
                raise ValueError("Wrong result scope")
            from vericlue_ml.common.result import Evidence

            result.evidence.append(
                Evidence(type="text", name="source_audio_sha256", value=sources["audio"])
            )
            return result
        except Exception as exc:
            self._failed = True
            self.close()
            return ModuleResult(
                module=KINDS[kind],
                model_version="unavailable",
                status="error",
                gate="unclear",
                error_code="E_TIMEOUT" if isinstance(exc, queue.Empty) else "E_INTERNAL",
                latency_ms=0,
            )
