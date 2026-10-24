"""One microphone/inference job at a time, independent of Tk and product routes."""

from __future__ import annotations

import hashlib
import importlib.metadata
import queue
import threading
from datetime import UTC, datetime
from typing import Any

from vericlue_ml.eval.microphone import record_microphone
from vericlue_ml.eval.report import git_revision


class VoiceTrial:
    """GUI polls bounded events; cancellation discards results and forbids overlap."""

    def __init__(self, detector: Any, *, device: int | None = None, recorder=record_microphone):
        self.detector, self.device, self.recorder = detector, device, recorder
        self.events = queue.SimpleQueue()
        self.stop = threading.Event()
        self.cancelled = threading.Event()
        self.active = False
        self.closed = False
        self.thread: threading.Thread | None = None

    def start(self, prompt: str) -> bool:
        """Call only after the user's record action; never start a second job."""
        if self.active or self.closed:
            return False
        self.active = True
        self.stop.clear()
        self.cancelled.clear()
        self.thread = threading.Thread(target=self._work, args=(prompt,), daemon=True)
        self.thread.start()
        return True

    def finish(self) -> None:
        """Stop capture, then check the captured sentence."""
        self.stop.set()

    def cancel(self) -> None:
        """Stop capture and discard any in-flight native inference result."""
        self.cancelled.set()
        self.stop.set()

    def close(self) -> None:
        """Request release without blocking the UI on OS/model work."""
        self.closed = True
        self.cancel()

    def _work(self, prompt: str) -> None:
        recording = None
        payload = None
        error = None
        try:
            recording = self.recorder(
                self.stop,
                device=self.device,
                started=lambda: self.events.put(("recording", None)),
            )
            if self.cancelled.is_set():
                return
            self.events.put(("processing", None))
            result = self.detector.predict_samples(
                recording.samples, recording.sample_rate, prompt=prompt
            )
            if self.cancelled.is_set():
                return
            asr = self.detector.asr
            payload = {
                "created_at": datetime.now(UTC).isoformat(),
                "commit": git_revision(),
                "model_version": self.detector.version,
                "model_revision": asr.config["revision"],
                "expected_model_hashes": dict(asr.config.get("sha256", {})),
                "verified_model_hashes": dict(asr.model_hashes),
                "model_loaded": asr._model is not None,
                "dataset": "local_microphone_diagnostic_not_accuracy_evaluation",
                "sample_count": 1,
                "prompt_source": "local_random_not_server_authenticated",
                "expected_text": prompt,
                "sample_rate": recording.sample_rate,
                "recorded_seconds": len(recording.samples) / recording.sample_rate,
                "pcm_float32_sha256": hashlib.sha256(
                    recording.samples.astype("<f4", copy=False).tobytes()
                ).hexdigest(),
                "runtime": {
                    name: _version(name)
                    for name in ("transformers", "torch", "numpy", "sounddevice")
                },
                "result": result.to_contract(),
            }
        except Exception:
            # No native exception text, paths or device identifiers in the GUI/report.
            error = "Không thể thu hoặc xử lý âm thanh. Kiểm tra micro, quyền truy cập và runtime."
        finally:
            if recording is not None:
                recording.samples.fill(0)
            self.events.put(("done", (payload, error)))

    def poll(self) -> list[tuple[str, Any]]:
        """Only the UI thread consumes events and unlocks the next take."""
        result = []
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            if kind == "done":
                self.active = False
                if self.cancelled.is_set() or self.closed:
                    value = (None, None)
            elif self.cancelled.is_set() or self.closed:
                continue
            result.append((kind, value))
        return result


def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"
