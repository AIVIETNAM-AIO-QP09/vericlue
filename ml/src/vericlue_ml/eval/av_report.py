"""JSON-safe metadata for one RAM A/V take; never serialize frames or PCM."""

import hashlib
import importlib.metadata
from datetime import UTC, datetime

from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval.nes2net_voice import runtime_versions
from vericlue_ml.eval.report import git_revision


def capture_metadata(recording) -> dict:
    return {
        **recording.metadata,
        "video_sha256": recording.video_sha256(),
        "pcm_float32_sha256": hashlib.sha256(
            recording.samples.astype("<f4", copy=False).tobytes()
        ).hexdigest(),
    }


def lipsync_payload(detector, recording, prompt: str) -> dict:
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": git_revision(),
        "sample_count": 1,
        "dataset": "local_av_lipsync_not_accuracy_evaluation",
        "runtime": runtime_versions(),
        "capture": capture_metadata(recording),
    }
    for package in ("av", "opencv-contrib-python", "onnxruntime", "pillow"):
        try:
            payload["runtime"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            payload["runtime"][package] = None
    try:
        result = detector.predict_recording(recording, prompt=prompt)
        payload.update(detector.provenance())
    except Exception:
        result = ModuleResult(
            module="lipsync",
            model_version=detector.version,
            status="error",
            gate="unclear",
            error_code="E_INTERNAL",
            latency_ms=0,
        )
    payload["result"] = result.to_contract()
    return payload
