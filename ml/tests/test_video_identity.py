"""Integration behavior of head motion -> decoded views -> identity, without model weights."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.face.pad import PadError
from vericlue_ml.presence import video_identity as pipeline
from vericlue_ml.presence.landmarks import FaceObservation
from vericlue_ml.presence.views import SelectedFrame


def inputs():
    return DetectorInput(
        session_id="ses_video_identity",
        video=Path("server-video.mp4"),
        reference_image=Path("portrait.png"),
        images=[Path("client-do-not-open.png")],
        image_roles=["front"],
        signals={"head_turn": {"gate": "pass"}, "view_times_ms": {"left": 0}},
        metadata={
            "challenge_id": "ch_video",
            "expected_challenge": {
                "challenge_id": "ch_video",
                "dynamic": {
                    "version": 1,
                    "session_id": "ses_video_identity",
                    "head_start_at_ms": 12000,
                    "head_duration_ms": 6000,
                    "frontal_capture_at_ms": 1000,
                    "head_turns": ["left", "right", "center"],
                },
            },
        },
    )


class Reader:
    def __init__(self, *, no_motion=False, bad_role=None, no_face=False, reverse=False):
        self.no_motion, self.bad_role, self.no_face = no_motion, bad_role, no_face
        self.reverse = reverse
        self.preloads, self.observed = [], []

    def preload(self, **kwargs):
        self.preloads.append(kwargs)

    def extract(self, *args, **kwargs):
        return [
            FaceObservation(
                float(t),
                1,
                yaw_deg=0.0
                if self.no_motion
                else (-1 if self.reverse else 1)
                * (28.0 if 12500 <= t < 14000 else -28.0 if 14500 <= t < 16000 else 0.0),
                pitch_deg=0.0,
                roll_deg=0.0,
            )
            for t in range(11500, 18001, 100)
        ]

    def observe(self, frame, *, at_ms):
        value = int(frame[0, 0, 0])
        self.observed.append((value, at_ms))
        if self.no_face:
            return FaceObservation(at_ms, 0)
        return FaceObservation(
            at_ms,
            1,
            yaw_deg=0.0 if value == self.bad_role else {1: 0.0, 2: 28.0, 3: -28.0}[value],
            pitch_deg=0.0,
            roll_deg=0.0,
        )


class Matcher:
    version = "synthetic-identity@unit-test"

    def __init__(self):
        self.preloads, self.calls = [], []

    def preload(self, **kwargs):
        self.preloads.append(kwargs)

    def predict_frames(self, inp, frames):
        self.calls.append((inp, frames))
        return ModuleResult(
            module=Module.FACE_MATCH,
            model_version=self.version,
            status=Status.DEGRADED,
            gate=Gate.UNCLEAR,
            quality={"threshold_available": False},
            latency_ms=0,
        )


class Deepfake:
    version = "synthetic-gend@unit-test"
    frames_version = version + "+headturn-3views-v1"

    def __init__(self, broken=False):
        self.preloads, self.calls, self.broken = [], [], broken

    def preload(self, **kwargs):
        self.preloads.append(kwargs)
        if self.broken:
            raise PadError("private/gend/path", ErrorCode.E_INTEGRITY)

    def predict_frames(self, inp, frames):
        self.calls.append(frames)
        return ModuleResult(
            module=Module.FACE_DEEPFAKE,
            model_version=self.frames_version,
            status=Status.OK,
            score=0.7,
            latency_ms=0,
        )


class Pad(Deepfake):
    version = "synthetic-fsvfm@unit-test"
    frames_version = version + "+headturn-3views-max-v1"

    def predict_frames(self, inp, frames):
        result = super().predict_frames(inp, frames)
        result.module = Module.FACE_PAD
        return result


def setup(monkeypatch):
    selections = []
    monkeypatch.setattr(pipeline, "video_sha256", lambda path: "a" * 64)

    def select(path, targets):
        selections.append((path, targets))
        return {
            role: SelectedFrame(
                target,
                target,
                np.full((112, 112, 3), {"front": 1, "left": 2, "right": 3}[role], dtype=np.uint8),
            )
            for role, target in targets.items()
        }

    monkeypatch.setattr(pipeline, "select_video_frames", select)
    return selections


def test_pipeline_owns_view_roles_rechecks_pixels_and_keeps_missing_threshold_unclear(monkeypatch):
    selections = setup(monkeypatch)
    reader, matcher = Reader(), Matcher()
    inp = inputs()
    result = pipeline.match_video_views(
        inp, reader=reader, matcher=matcher, models_dir=Path("model-root"), device="cpu"
    )
    assert result.head_turn.gate == Gate.PASS
    assert result.face_match.status == Status.DEGRADED and result.face_match.gate == Gate.UNCLEAR
    assert len(matcher.calls) == 1 and len(reader.observed) == 3
    assert set(matcher.calls[0][1]) == {"front", "left", "right"}
    assert selections[0][1] == {"front": 1000, "left": 13200, "right": 15200}
    assert matcher.preloads == [{"models_dir": Path("model-root"), "device": "cpu"}]
    assert result.face_match.quality["views_from_video"] is True
    assert result.face_match.quality["depth_verified"] is False
    assert inp.images == [Path("client-do-not-open.png")]  # Input not mutated.
    report = result.to_contract()
    assert "portrait.png" not in str(report) and "client-do-not-open" not in str(report)
    evidence = next(e.value for e in result.face_match.evidence if e.name == "selected_frames")
    assert all(len(row["pixels_sha256"]) == 64 for row in evidence.values())
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "packages/contracts/schemas/module_result.schema.json"
        ).read_text(encoding="utf-8")
    )
    for entry in report.values():
        jsonschema.validate(entry, schema)


def test_reverse_head_order_still_assigns_correct_left_right_roles(monkeypatch):
    selections = setup(monkeypatch)
    inp, matcher = inputs(), Matcher()
    inp.metadata["expected_challenge"]["dynamic"]["head_turns"] = ["right", "left", "center"]
    result = pipeline.match_video_views(inp, reader=Reader(reverse=True), matcher=matcher)
    assert result.head_turn.gate == Gate.PASS and len(matcher.calls) == 1
    assert selections[0][1]["right"] < selections[0][1]["left"]


def test_optional_gend_uses_same_pixel_objects_and_has_separate_measurement(monkeypatch):
    setup(monkeypatch)
    matcher, deepfake = Matcher(), Deepfake()
    result = pipeline.match_video_views(
        inputs(), reader=Reader(), matcher=matcher, deepfake=deepfake
    )
    assert result.face_match.status == Status.DEGRADED
    assert result.face_deepfake.status == Status.OK and result.face_deepfake.score == 0.7
    assert result.face_deepfake.prob_attack is None and result.face_deepfake.gate is None
    assert all(deepfake.calls[0][role] is matcher.calls[0][1][role] for role in deepfake.calls[0])
    assert set(result.to_contract()) == {"head_turn", "face_match", "face_deepfake"}
    assert result.face_deepfake.quality["depth_verified"] is False


def test_head_failure_blocks_gend_without_model_load(monkeypatch):
    setup(monkeypatch)
    deepfake = Deepfake()
    result = pipeline.match_video_views(
        inputs(), reader=Reader(no_motion=True), matcher=Matcher(), deepfake=deepfake
    )
    assert (
        result.face_deepfake.status == Status.DEGRADED and result.face_deepfake.gate == Gate.UNCLEAR
    )
    assert not deepfake.preloads and not deepfake.calls


def test_optional_pad_gend_match_share_exact_pixels_and_provenance(monkeypatch):
    setup(monkeypatch)
    pad, deepfake, matcher = Pad(), Deepfake(), Matcher()
    result = pipeline.match_video_views(
        inputs(), reader=Reader(), matcher=matcher, pad=pad, deepfake=deepfake
    )
    assert result.face_pad.status == Status.OK and result.face_pad.score == 0.7
    assert result.face_pad.prob_attack is None and result.face_pad.gate is None
    assert all(
        pad.calls[0][role] is deepfake.calls[0][role] is matcher.calls[0][1][role]
        for role in pad.calls[0]
    )
    evidence = next(e.value for e in result.face_pad.evidence if e.name == "source_video_sha256")
    assert evidence == "a" * 64
    assert "face_pad" in result.to_contract()


@pytest.mark.parametrize("failure", ["head", "source", "pose", "pad"])
def test_pad_blocks_early_and_model_failure_preserves_other_measurements(monkeypatch, failure):
    setup(monkeypatch)
    pad, deepfake, matcher = Pad(broken=failure == "pad"), Deepfake(), Matcher()
    if failure == "source":
        hashes = iter(["a" * 64, "b" * 64])
        monkeypatch.setattr(pipeline, "video_sha256", lambda path: next(hashes))
    result = pipeline.match_video_views(
        inputs(),
        reader=Reader(no_motion=failure == "head", bad_role=2 if failure == "pose" else None),
        matcher=matcher,
        deepfake=deepfake,
        pad=pad,
    )
    assert result.face_pad.status != Status.OK and result.face_pad.prob_attack is None
    if failure == "pad":
        assert result.face_pad.error_code == "E_INTEGRITY"
        assert result.face_deepfake.status == Status.OK and matcher.calls
    else:
        assert not pad.preloads and not pad.calls


@pytest.mark.parametrize("broken", ["matcher", "gend"])
def test_one_model_failure_preserves_other_independent_measurement(monkeypatch, broken):
    setup(monkeypatch)
    matcher, deepfake = Matcher(), Deepfake(broken=broken == "gend")
    if broken == "matcher":

        def fail(**kwargs):
            raise PadError("private/lvface/path", ErrorCode.E_INTERNAL)

        matcher.preload = fail
    result = pipeline.match_video_views(
        inputs(), reader=Reader(), matcher=matcher, deepfake=deepfake
    )
    if broken == "matcher":
        assert result.face_match.status == Status.ERROR and result.face_deepfake.status == Status.OK
    else:
        assert (
            result.face_deepfake.status == Status.ERROR
            and result.face_match.status == Status.DEGRADED
        )
    assert result.head_turn.gate == Gate.PASS and "private/" not in str(result.to_contract())


def test_changed_source_invalidates_gend_before_preload(monkeypatch):
    setup(monkeypatch)
    hashes = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr(pipeline, "video_sha256", lambda path: next(hashes))
    deepfake = Deepfake()
    result = pipeline.match_video_views(
        inputs(), reader=Reader(), matcher=Matcher(), deepfake=deepfake
    )
    assert (
        result.face_deepfake.status == Status.ERROR
        and result.face_deepfake.error_code == "E_INTEGRITY"
    )
    assert not deepfake.preloads


def test_head_failure_never_selects_frames_or_preloads_matcher(monkeypatch):
    selections = setup(monkeypatch)
    reader, matcher = Reader(no_motion=True), Matcher()
    result = pipeline.match_video_views(inputs(), reader=reader, matcher=matcher)
    assert result.head_turn.gate == Gate.FAIL and result.face_match.gate == Gate.UNCLEAR
    assert not selections and not reader.observed and not matcher.preloads and not matcher.calls


@pytest.mark.parametrize("kind", ["wrong_pose", "no_face", "missing_pose", "multiple_faces"])
def test_selected_frame_must_itself_have_one_face_and_correct_pose(monkeypatch, kind):
    setup(monkeypatch)
    reader, matcher = (
        Reader(bad_role=2 if kind == "wrong_pose" else None, no_face=kind == "no_face"),
        Matcher(),
    )
    if kind in {"missing_pose", "multiple_faces"}:
        original = reader.observe
        reader.observe = lambda *args, **kwargs: replace(
            original(*args, **kwargs),
            **({"yaw_deg": None} if kind == "missing_pose" else {"face_count": 2}),
        )
    result = pipeline.match_video_views(inputs(), reader=reader, matcher=matcher)
    assert result.face_match.status in {Status.DEGRADED, Status.NOT_APPLICABLE}
    assert result.face_match.gate == Gate.UNCLEAR and not matcher.preloads and not matcher.calls


def test_modified_source_invalidates_both_results_before_identity_load(monkeypatch):
    setup(monkeypatch)
    hashes = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr(pipeline, "video_sha256", lambda path: next(hashes))
    matcher = Matcher()
    result = pipeline.match_video_views(inputs(), reader=Reader(), matcher=matcher)
    assert all(
        r.status == Status.ERROR and r.error_code == "E_INTEGRITY" and r.gate == Gate.UNCLEAR
        for r in (result.head_turn, result.face_match)
    )
    assert not matcher.preloads


@pytest.mark.parametrize(
    "times",
    [
        {"front": 900, "left": 13200, "right": 15200},
        {"front": 1000, "left": 15200, "right": 13200},
        {"front": 1000, "left": float("nan"), "right": 15200},
    ],
)
def test_invalid_head_result_timestamps_cannot_become_frame_selection(monkeypatch, times):
    selections = setup(monkeypatch)
    head = ModuleResult(
        module=Module.HEAD_TURN,
        model_version="synthetic@unit-test",
        status=Status.OK,
        gate=Gate.PASS,
        latency_ms=0,
        evidence=[Evidence(type="timeseries", name="view_times_ms", value=times)],
    )
    monkeypatch.setattr(
        pipeline, "HeadTurnDetector", lambda reader: SimpleNamespace(predict=lambda inp: head)
    )
    matcher = Matcher()
    result = pipeline.match_video_views(inputs(), reader=Reader(), matcher=matcher)
    assert result.head_turn.gate == Gate.UNCLEAR and result.face_match.error_code == "E_INTEGRITY"
    assert not selections and not matcher.preloads


def test_bad_identity_weights_preserve_integrity_error_without_invalidating_motion(monkeypatch):
    setup(monkeypatch)
    matcher = Matcher()

    def fail(**kwargs):
        raise PadError("private/model/path", ErrorCode.E_INTEGRITY)

    matcher.preload = fail
    result = pipeline.match_video_views(inputs(), reader=Reader(), matcher=matcher)
    assert result.head_turn.status == Status.OK and result.head_turn.gate == Gate.PASS
    assert (
        result.face_match.status == Status.ERROR and result.face_match.error_code == "E_INTEGRITY"
    )
    assert result.face_match.gate == Gate.UNCLEAR and not matcher.calls
    assert "private/model" not in str(result.to_contract())


@pytest.mark.parametrize("kind", ["wrong_session", "no_video", "no_reference"])
def test_invalid_inputs_stop_before_model_preload(monkeypatch, kind):
    setup(monkeypatch)
    inp, reader, matcher = inputs(), Reader(), Matcher()
    if kind == "wrong_session":
        inp.session_id = "other-session"
    elif kind == "no_video":
        inp.video = None
    else:
        inp.reference_image = None
    result = pipeline.match_video_views(inp, reader=reader, matcher=matcher)
    assert result.head_turn.gate == Gate.UNCLEAR and result.face_match.gate == Gate.UNCLEAR
    assert not reader.preloads and not matcher.preloads


def test_native_decoder_error_is_sanitized_and_never_invokes_matcher(monkeypatch):
    setup(monkeypatch)

    def fail(*args):
        raise RuntimeError("private/biometric/storage/path")

    monkeypatch.setattr(pipeline, "select_video_frames", fail)
    matcher = Matcher()
    result = pipeline.match_video_views(inputs(), reader=Reader(), matcher=matcher)
    assert result.face_match.status == Status.ERROR and not matcher.calls
    assert "private/biometric" not in str(result.to_contract())
