"""Bounded in-memory A/V from one container, on the audio track's original PTS origin."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field

import numpy as np


@dataclass
class EncodedVideoFrame:
    at_s: float
    jpeg: bytearray


@dataclass
class AVRecording:
    samples: np.ndarray
    sample_rate: int
    frames: list[EncodedVideoFrame]
    metadata: dict = field(default_factory=dict)

    def video_sha256(self) -> str:
        """Bind ordered JPEG bytes and their original relative presentation timestamps."""
        digest = hashlib.sha256()
        for frame in self.frames:
            digest.update(struct.pack("<dQ", frame.at_s, len(frame.jpeg)))
            digest.update(frame.jpeg)
        return digest.hexdigest()

    def wipe(self) -> None:
        """Release main buffers; native/temporary copies are not guaranteed secure erasure."""
        self.samples.fill(0)
        for frame in self.frames:
            frame.jpeg[:] = b"\0" * len(frame.jpeg)
        self.frames.clear()
