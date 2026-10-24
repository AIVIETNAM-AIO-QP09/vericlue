"""Explicitly started, bounded RAM-only recording for the internal voice lab.

Uses sounddevice.InputStream blocking reads on a worker, not a real-time Python
callback. API: spatialaudio/python-sounddevice v0.5.6, InputStream.read/close.
No microphone is opened at import, construction, or device enumeration.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

MAX_RECORD_SECONDS = 20


class RecordingError(RuntimeError):
    """Capture unavailable or incomplete; never submit partial input as accepted."""


@dataclass
class Recording:
    """Mono float32 PCM; caller discards it after inference."""

    samples: np.ndarray
    sample_rate: int


def record_microphone(
    stop: threading.Event,
    *,
    device: int | None = None,
    started: Callable[[], None] = lambda: None,
    backend: Any = None,
) -> Recording:
    """Worker-owned stream; stop after user action or 20 seconds, always close it."""
    stream = None
    try:
        if stop.is_set():
            raise RecordingError("Recording cancelled before opening microphone")
        if backend is None:
            import sounddevice as backend

        rate = float(backend.query_devices(device, "input")["default_samplerate"])
        if not rate.is_integer() or not 8000 <= rate <= 192000:
            raise RecordingError("Unsupported microphone sample rate")
        rate = int(rate)
        block = rate // 20  # 50 ms blocking reads, no PortAudio callback allocations.
        remaining = MAX_RECORD_SECONDS * rate
        stream = backend.InputStream(
            device=device, samplerate=rate, channels=1, dtype="float32", blocksize=block
        )
        # Cancellation while the OS opens the device must not start a new capture.
        if stop.is_set():
            raise RecordingError("Recording cancelled while opening microphone")
        stream.start()
        started()
        chunks = []
        while remaining > 0 and not stop.is_set():
            count = min(block, remaining)
            data, overflowed = stream.read(count)
            if (
                overflowed
                or not isinstance(data, np.ndarray)
                or data.shape != (count, 1)
                or data.dtype != np.float32
                or not np.isfinite(data).all()
                or np.any(np.abs(data) > 1)
            ):
                raise RecordingError("Microphone input incomplete or invalid")
            chunks.append(data[:, 0].copy())
            remaining -= count
        if not chunks:
            raise RecordingError("No microphone samples")
        return Recording(np.concatenate(chunks), rate)
    except Exception as exc:
        raise RecordingError("Cannot capture complete microphone audio") from exc
    finally:
        if stream is not None:
            try:
                stream.abort()
            finally:
                # Even abort failure must close; close failure invalidates this take too.
                stream.close()
