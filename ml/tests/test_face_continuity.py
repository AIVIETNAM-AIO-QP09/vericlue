"""Cross-stage identity with synthetic pixels/PCM/embeddings; no weights or people."""

import hashlib
import json
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Evidence, ModuleResult
from vericlue_ml.face import continuity
from vericlue_ml.face.continuity import FACE_VOICE_VERSION, FaceContinuityDetector, wav_duration
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION
from vericlue_ml.presence.landmarks import FaceObservation, LandmarkError
from vericlue_ml.presence.views import SelectedFrame


def pcm(path, *, frames=64000, rate=16000, channels=1):
    with wave.open(str(path), "wb") as stream:
        stream.setparams((channels, 2, rate, frames, "NONE", "not compressed"))
        stream.writeframes(b"\x01\0" * frames * channels)
    return path


def fixture(monkeypatch, tmp_path, *, threshold=None, similarities=(1, 1, 1)):
    reference = np.full((112, 112, 3), 10, np.uint8)
    calls = []

    class Matcher:
        def preload(self, **kwargs):
            pass

        def embed_frames(self, frames):
            calls.append(frames)
            result = {}
            for i, (name, pixels) in enumerate(frames.items()):
                value = np.zeros(512, np.float32)
                c = 1 if i == 0 else similarities[i - 1]
                value[:2] = [c, np.sqrt(1 - c * c)]
                result[name] = value, hashlib.sha256(pixels.tobytes()).hexdigest()
            return result

    reader = SimpleNamespace(
        preload=lambda **kw: None,
        observe=lambda pixels, at_ms: FaceObservation(
            at_ms, 1, yaw_deg=0.0, pitch_deg=0.0, roll_deg=0.0
        ),
    )
    artifact = None
    if threshold is not None:
        artifact = tmp_path / "synthetic-calibration.json"
        artifact.write_text(
            json.dumps(
                {
                    "model_version": FACE_VOICE_VERSION,
                    "preprocessing": "arcface112-rgb-minus1to1-v1",
                    "threshold": float(threshold),
                    "split": "calib_ltt",
                    "dataset": "synthetic-not-calibration",
                    "pairs": 4,
                    "subjects": 2,
                    "source_commit": "e" * 40,
                    "predictions_sha256": "f" * 64,
                }
            ),
            encoding="utf-8",
        )
    model = FaceContinuityDetector(Matcher(), reader, calibration_path=artifact)
    monkeypatch.setattr(
        continuity, "video_sha256", lambda p: "a" * 64 if p.name == "face.mp4" else "b" * 64
    )
    monkeypatch.setattr(
        continuity, "select_frontal_frame", lambda p, t: SelectedFrame(t, 240, reference)
    )
    selected = []

    def pick(path, targets):
        selected.append(targets)
        return {
            name: SelectedFrame(target, target + 10, np.full((112, 112, 3), 20 + i, np.uint8))
            for i, (name, target) in enumerate(targets.items())
        }

    monkeypatch.setattr(continuity, "select_timed_frames", pick)
    approved = ModuleResult(
        module="face_match",
        model_version=VIDEO_MATCH_VERSION,
        status="ok",
        gate="pass",
        latency_ms=0,
        evidence=[
            Evidence(type="text", name="source_video_sha256", value="a" * 64),
            Evidence(
                type="scalar",
                name="selected_frontal_frame",
                value={
                    "target_ms": 250,
                    "at_ms": 240,
                    "pixels_sha256": hashlib.sha256(reference.tobytes()).hexdigest(),
                },
            ),
        ],
    )
    inp = DetectorInput(
        session_id="ses_continuity",
        reference_video=Path("face.mp4"),
        video=Path("voice.mp4"),
        audio=pcm(tmp_path / "speech.wav"),
        images=[Path("ignored-client-still.jpg")],
        metadata={
            "challenge_id": "ch_face",
            "voice_challenge_id": "vc_current",
            "expected_voice_challenge_id": "vc_current",
            "audio_offset_ms": 600,
            "expected_challenge": {
                "challenge_id": "ch_face",
                "baseline_ms": 1000,
                "dynamic": {
                    "session_id": "ses_continuity",
                    "version": 1,
                    "frontal_capture_at_ms": 250,
                },
            },
            "face_reference_result": approved.to_contract(),
        },
    )
    return model, inp, calls, selected


def test_default_is_raw_and_sampling_uses_actual_wav_and_signed_offset(monkeypatch, tmp_path):
    model, inp, calls, selected = fixture(monkeypatch, tmp_path)
    result = model.predict(inp)
    assert result.status == "degraded" and result.gate == "unclear" and result.score == 0
    assert result.prob_attack is None
    assert selected == [{"early": 1000, "middle": 2600, "late": 4200}]
    assert set(calls[0]) == {"reference", "early", "middle", "late"}
    assert "embedding" not in result.model_dump_json()
    assert result.quality["coverage"] == "three_samples_not_full_video"
    assert all(e.value for e in result.evidence if e.name.endswith("sha256"))


@pytest.mark.parametrize(
    "similarities,gate", [((0.9, 0.9, 0.9), "pass"), ((0.9, 0.1, 0.9), "fail")]
)
def test_every_sample_must_meet_own_threshold(monkeypatch, tmp_path, similarities, gate):
    model, inp, _, _ = fixture(monkeypatch, tmp_path, threshold=0.5, similarities=similarities)
    result = model.predict(inp)
    assert result.status == "ok" and result.gate == gate
    assert result.score == pytest.approx(1 - min(similarities))


@pytest.mark.parametrize(
    "fault",
    [
        "session",
        "face_attempt",
        "voice_attempt",
        "bool_offset",
        "bad_offset",
        "missing_video",
        "missing_reference",
        "source",
        "pixels",
        "timestamp",
        "duplicate_evidence",
        "model",
        "multi_face",
        "pose",
        "reused_clip",
        "mutated_voice",
        "mutated_audio",
    ],
)
def test_wrong_binding_or_sources_never_pass(monkeypatch, tmp_path, fault):
    model, inp, _, _ = fixture(monkeypatch, tmp_path, threshold=0.5)
    ref = inp.metadata["face_reference_result"]
    if fault == "session":
        inp.session_id = "ses_other"
    elif fault == "face_attempt":
        inp.metadata["challenge_id"] = "ch_other"
    elif fault == "voice_attempt":
        inp.metadata["voice_challenge_id"] = "vc_other"
    elif fault == "bool_offset":
        inp.metadata["audio_offset_ms"] = True
    elif fault == "bad_offset":
        inp.metadata["audio_offset_ms"] = 5001
    elif fault == "missing_video":
        inp.video = None
    elif fault == "missing_reference":
        inp.reference_video = None
    elif fault == "source":
        ref["evidence"][0]["value"] = "c" * 64
    elif fault == "pixels":
        ref["evidence"][1]["value"]["pixels_sha256"] = "c" * 64
    elif fault == "timestamp":
        ref["evidence"][1]["value"]["at_ms"] = 250
    elif fault == "duplicate_evidence":
        ref["evidence"].append(ref["evidence"][0])
    elif fault == "model":
        ref["model_version"] = "wrong-version"
    elif fault in {"multi_face", "pose"}:
        model.reader.observe = lambda pixels, at_ms: FaceObservation(
            at_ms,
            2 if fault == "multi_face" else 1,
            yaw_deg=30.0 if fault == "pose" else 0.0,
            pitch_deg=0.0,
            roll_deg=0.0,
        )
    elif fault == "reused_clip":
        inp.video = inp.reference_video
    elif fault == "mutated_voice":
        count = [0]

        def digest(path):
            if path.name == "face.mp4":
                return "a" * 64
            count[0] += 1
            return ("b" if count[0] == 1 else "c") * 64

        monkeypatch.setattr(continuity, "video_sha256", digest)
    else:
        original = model.matcher.embed_frames

        def mutate(frames):
            pcm(inp.audio, frames=80000)
            return original(frames)

        model.matcher.embed_frames = mutate
    result = model.predict(inp)
    assert result.gate == "unclear" and result.status != "ok"


def test_old_cccd_artifact_cannot_be_reused_and_failure_is_sticky(monkeypatch, tmp_path):
    model, inp, _, _ = fixture(monkeypatch, tmp_path, threshold=0.5)
    payload = json.loads(model.calibration_path.read_text())
    payload["model_version"] = VIDEO_MATCH_VERSION
    model.calibration_path.write_text(json.dumps(payload))
    assert model.predict(inp).gate == "unclear"
    payload["model_version"] = FACE_VOICE_VERSION
    model.calibration_path.write_text(json.dumps(payload))
    assert model.predict(inp).gate == "unclear"


@pytest.mark.parametrize("status,gate", [("degraded", "pass"), ("error", "pass"), ("ok", "fail")])
def test_uncertain_reference_never_qualifies_even_if_faces_match(
    monkeypatch, tmp_path, status, gate
):
    model, inp, _, _ = fixture(monkeypatch, tmp_path, threshold=0.5)
    inp.metadata["face_reference_result"].update(status=status, gate=gate)
    result = model.predict(inp)
    assert result.status == "degraded" and result.gate == "unclear" and result.score == 0


@pytest.mark.parametrize(
    "params", [{"frames": 8000}, {"frames": 160001}, {"rate": 8000}, {"channels": 2}]
)
def test_pcm_bounds_are_enforced(tmp_path, params):
    with pytest.raises(LandmarkError):
        wav_duration(pcm(tmp_path / "invalid.wav", **params))


def test_reference_video_field_matches_internal_contract_and_stays_out_of_http():
    from vericlue_ml.router.profiles import get_profile

    schema = json.loads(
        (
            Path(__file__).parents[2] / "packages/contracts/schemas/detector_input.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert set(schema["properties"]) == set(DetectorInput.model_fields)
    assert "reference_video" in schema["properties"]
    assert all("face_continuity" not in get_profile(name).modules for name in ("full", "mvp"))


@pytest.mark.parametrize("fault", ["truncated", "invalid_header"])
def test_bad_wav_never_uses_header_duration_alone(tmp_path, fault):
    path = pcm(tmp_path / "bad.wav")
    path.write_bytes(path.read_bytes()[:80] if fault == "truncated" else b"not-a-wav")
    with pytest.raises(LandmarkError) as error:
        wav_duration(path)
    assert error.value.code == "E_DECODE"
