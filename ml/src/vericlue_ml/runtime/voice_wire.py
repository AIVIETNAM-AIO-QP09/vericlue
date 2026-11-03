"""Bounded worker protocol; paths must resolve under server-owned media storage."""

import hashlib
import json
from pathlib import Path

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.voice.content_backend import content_model_version, validate_content_backend

PROTOCOL = "vericlue-session-voice-v1"
MAX_REQUEST = 65536
MAX_REPLY = 1 << 20
KINDS = {
    "content": "voice_challenge",
    "timing": "voice_challenge",
    "lipsync": "lipsync",
    "spoof": "voice_spoof",
}


def expected_version(kind: str, manual_demo=None, *, content_backend: str = "qwen06") -> str:
    validate_content_backend(content_backend, manual=manual_demo is not None)
    if kind not in KINDS:
        raise ValueError("Unknown voice worker kind")
    if manual_demo is not None and kind in {"spoof", "lipsync"}:
        from vericlue_ml.voice.antispoof import AntiDeepfakeDetector
        from vericlue_ml.voice.syncnet import SyncNetDetector

        raw = AntiDeepfakeDetector().version if kind == "spoof" else SyncNetDetector().version
        return raw + manual_demo.version_suffix
    if kind == "content":
        return content_model_version(content_backend)
    elif kind == "timing":
        from vericlue_ml.voice.reading_timing import VERSION
    elif kind == "spoof":
        from vericlue_ml.voice.nes2net_timeline import VERSION
    else:
        from vericlue_ml.voice.syncnet import SyncNetDetector

        return SyncNetDetector().version + "+session-offset-v1"
    return VERSION


def canonical(value: dict) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def source_hashes(inp: DetectorInput, root: Path, kind: str) -> dict[str, str]:
    """Do not follow arbitrary URLs, playlist files or references outside MEDIA_DIR."""
    sources = {"audio": (inp.audio, 32 << 20)}
    if kind == "lipsync":
        sources["video"] = (inp.video, 64 << 20)
    result = {}
    for role, (path, limit) in sources.items():
        if path is None or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("Missing or untrusted source")
        if not 0 < path.stat().st_size <= limit:
            raise ValueError("Invalid source bounds")
        with path.open("rb") as handle:
            if role == "video":
                header = handle.read(12)
                if not (
                    header.startswith(b"\x1aE\xdf\xa3")
                    or header[4:8] == b"ftyp"
                    or header.startswith(b"RIFF")
                    and header[8:12] == b"AVI "
                ):
                    raise ValueError("Not a local video container")
                handle.seek(0)
            result[role] = hashlib.file_digest(handle, "sha256").hexdigest()
    return result


def worker_scope(manual_demo=None, *, content_backend: str = "qwen06") -> dict:
    """Private protocol binding; standard framing stays backward compatible."""
    validate_content_backend(content_backend, manual=manual_demo is not None)
    scope = (
        {"mode": "manual_full_demo", "policy_id": manual_demo.policy_id}
        if manual_demo is not None
        else {}
    )
    if content_backend == "qwen17":
        scope["content_model_version"] = content_model_version(content_backend)
    return scope


def worker_hello(manual_demo=None, warmup_kinds=(), *, content_backend: str = "qwen06") -> dict:
    hello = {
        "protocol": PROTOCOL,
        "ready": True,
        **worker_scope(manual_demo, content_backend=content_backend),
    }
    if manual_demo is not None:
        hello["loaded_versions"] = {
            kind: expected_version(kind, manual_demo, content_backend=content_backend)
            for kind in warmup_kinds
        }
    return hello
