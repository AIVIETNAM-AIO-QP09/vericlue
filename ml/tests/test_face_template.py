"""Private template contract and provenance; synthetic pixels/vector, no weights."""

import hashlib
import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest
from pydantic import ValidationError
from test_video_frontal_match import inputs, setup

from vericlue_ml.common.result import Evidence, ModuleResult
from vericlue_ml.face.match import MatchError
from vericlue_ml.face.template import FaceTemplate
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION


def ready(monkeypatch):
    matcher, _ = setup(monkeypatch)
    frame = np.full((112, 112, 3), 42, np.uint8)
    pixels_hash = hashlib.sha256(frame.tobytes()).hexdigest()
    # Existing setup controls video/frame/pose; replace only identity scoring.
    monkeypatch.setattr(
        matcher,
        "predict_frames",
        lambda inp, frames: ModuleResult(
            module="face_match",
            model_version=VIDEO_MATCH_VERSION,
            status="ok",
            gate="pass",
            latency_ms=0,
        ),
    )
    monkeypatch.setattr(
        matcher, "_embedding", lambda pixels: (np.eye(1, 512, dtype=np.float32)[0], pixels_hash)
    )
    return matcher


def test_template_matches_internal_contract_and_never_enters_result(monkeypatch):
    matcher = ready(monkeypatch)
    inp = inputs()
    approved = matcher.predict(inp)
    template = matcher.enrollment_template(inp, approved)
    schema = json.loads(
        (
            Path(__file__).parents[2] / "packages/contracts/schemas/face_template.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.validate(template.model_dump(mode="json"), schema)
    assert set(FaceTemplate.model_fields) == set(schema["properties"])
    assert template.embedding[0] == 1 and len(template.embedding) == 512
    assert template.session_id == inp.session_id
    assert "embedding" not in approved.model_dump_json()
    assert "embedding" not in repr(template)
    assert FaceTemplate.model_validate_json(template.model_dump_json()) == template


@pytest.mark.parametrize(
    "fault", ["degraded", "unclear", "version", "video", "pixels", "duplicate", "pose"]
)
def test_unapproved_or_changed_provenance_cannot_extract_template(monkeypatch, fault):
    matcher = ready(monkeypatch)
    inp = inputs()
    approved = matcher.predict(inp)
    if fault == "degraded":
        approved.status = "degraded"
    elif fault == "unclear":
        approved.gate = "unclear"
    elif fault == "version":
        approved.model_version = "old-model"
    elif fault == "video":
        approved.evidence[0].value = "b" * 64
    elif fault == "pixels":
        approved.evidence[1].value["pixels_sha256"] = "b" * 64
    elif fault == "duplicate":
        approved.evidence.append(Evidence(type="text", name="source_video_sha256", value="a" * 64))
    else:
        monkeypatch.setattr(
            matcher.reader, "observe", lambda *a, **kw: (_ for _ in ()).throw(ValueError())
        )
    with pytest.raises(MatchError):
        matcher.enrollment_template(inp, approved)


@pytest.mark.parametrize("fault", ["short", "zero", "nan", "infinity", "not_unit"])
def test_invalid_private_vector_is_rejected(monkeypatch, fault):
    matcher = ready(monkeypatch)
    inp = inputs()
    template = matcher.enrollment_template(inp, matcher.predict(inp))
    vector = [1.0, *([0.0] * 511)]
    if fault == "short":
        vector.pop()
    elif fault == "zero":
        vector[0] = 0.0
    elif fault == "nan":
        vector[0] = float("nan")
    elif fault == "infinity":
        vector[0] = float("inf")
    else:
        vector[1] = 0.1
    with pytest.raises(ValidationError):
        FaceTemplate.model_validate({**template.model_dump(), "embedding": tuple(vector)})
