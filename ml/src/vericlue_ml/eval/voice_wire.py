"""Bounded JSON header + little-endian float32 PCM protocol, never pickle/media files."""

from __future__ import annotations

import hashlib
import json
import re
from typing import BinaryIO

import numpy as np

MAX_SAMPLES = 30 * 16000
MAX_HEADER = 1024
MAX_REPLY = 32768
PROTOCOL = "vericlue-nes2net-pcm-v1"


def pcm_bytes(samples: np.ndarray) -> bytes:
    """Only finite, bounded mono PCM; no implicit rate conversion here."""
    if (
        not isinstance(samples, np.ndarray)
        or samples.ndim != 1
        or samples.dtype != np.float32
        or not 0 < len(samples) <= MAX_SAMPLES
        or not np.isfinite(samples).all()
        or np.any(np.abs(samples) > 1)
    ):
        raise ValueError("Invalid bounded PCM")
    return samples.astype("<f4", copy=False).tobytes()


def encode_request(samples: np.ndarray, request_id: str) -> tuple[bytes, str]:
    """Serialize one take with byte count/hash; expected phrase never enters this channel."""
    if not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise ValueError("Invalid request id")
    raw = pcm_bytes(samples)
    checksum = hashlib.sha256(raw).hexdigest()
    header = {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "samples": len(samples),
        "sample_rate": 16000,
        "sha256": checksum,
    }
    return json.dumps(header).encode("ascii") + b"\n" + raw, checksum


def read_request(source: BinaryIO) -> tuple[dict, np.ndarray] | None:
    """Read one frame; malformed/truncated frames terminate the stream without inference."""
    line = source.readline(MAX_HEADER + 1)
    if not line:
        return None
    if len(line) > MAX_HEADER or not line.endswith(b"\n"):
        raise ValueError("Invalid header bounds")
    header = json.loads(line)
    if (
        not isinstance(header, dict)
        or set(header) != {"protocol", "request_id", "samples", "sample_rate", "sha256"}
        or header["protocol"] != PROTOCOL
        or not isinstance(header["request_id"], str)
        or not re.fullmatch(r"[0-9a-f]{32}", header["request_id"])
        or type(header["samples"]) is not int
        or not 0 < header["samples"] <= MAX_SAMPLES
        or type(header["sample_rate"]) is not int
        or header["sample_rate"] != 16000
        or not isinstance(header["sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", header["sha256"])
    ):
        raise ValueError("Invalid header")
    remaining = header["samples"] * 4
    raw = bytearray()
    while remaining:
        part = source.read(remaining)
        if not part:
            raise ValueError("Truncated PCM frame")
        raw.extend(part)
        remaining -= len(part)
    try:
        if hashlib.sha256(raw).hexdigest() != header["sha256"]:
            raise ValueError("PCM integrity mismatch")
        samples = np.frombuffer(raw, dtype="<f4").astype(np.float32, copy=True)
        pcm_bytes(samples)
        return header, samples
    finally:
        raw[:] = b"\0" * len(raw)


def encode_reply(payload: dict) -> bytes:
    """No nonfinite JSON or unbounded provider output on stdout."""
    raw = json.dumps(payload, ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
    if len(raw) > MAX_REPLY:
        raise ValueError("Oversized reply")
    return raw
