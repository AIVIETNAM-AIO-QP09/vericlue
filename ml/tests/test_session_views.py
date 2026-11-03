"""Selected session attack/consistency frames must match server schedule and observed pose."""

from types import SimpleNamespace

import numpy as np
import pytest
from test_video_frontal_match import inputs

from vericlue_ml.common.manual_demo import ManualDemoThresholds
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, ModuleResult, Status
from vericlue_ml.face.session_attack import SessionAttackDetector
from vericlue_ml.presence import session_views as selection
from vericlue_ml.presence.landmarks import FaceObservation, LandmarkError
from vericlue_ml.presence.views import SelectedFrame


@pytest.mark.parametrize("fault", [None, "head_failed", "time", "pose", "faces", "changed"])
def test_session_frame_selection_rejects_missing_or_wrong_evidence(monkeypatch, fault):
    inp = inputs()
    inp.metadata["expected_challenge"]["dynamic"].update(
        head_start_at_ms=12000, head_duration_ms=6000, head_turns=["left", "right", "center"]
    )
    times = {"front": 250, "left": 13000, "right": 15000}
    if fault == "time":
        times["front"] = 350
    head = ModuleResult(
        module="head_turn",
        model_version="synthetic",
        status="ok",
        gate="fail" if fault == "head_failed" else "pass",
        latency_ms=0,
        evidence=[Evidence(type="scalar", name="view_times_ms", value=times)],
    )
    monkeypatch.setattr(
        selection, "HeadTurnDetector", lambda *_: SimpleNamespace(predict=lambda _: head)
    )
    monkeypatch.setattr(
        selection, "video_sha256", lambda *_: "a" if fault != "changed" else next(hashes)
    )
    hashes = iter(["a", "b"])
    frames = {
        role: SelectedFrame(time, time, np.full((20, 20, 3), i, np.uint8))
        for i, (role, time) in enumerate(times.items())
    }
    monkeypatch.setattr(selection, "select_video_frames", lambda *_: frames)

    def observe(pixels, *, at_ms):
        yaw = {0: 0.0, 1: 28.0, 2: -28.0}[int(pixels[0, 0, 0])]
        return FaceObservation(
            at_ms,
            2 if fault == "faces" else 1,
            yaw_deg=0.0 if fault == "pose" else yaw,
            pitch_deg=0.0,
            roll_deg=0.0,
        )

    if fault is None:
        actual, checksum = selection.session_views(inp, SimpleNamespace(observe=observe))
        assert checksum == "a" and all(actual[role] is frames[role].bgr for role in frames)
    else:
        with pytest.raises(LandmarkError):
            selection.session_views(inp, SimpleNamespace(observe=observe))


@pytest.fixture
def adaptive_input():
    inp = inputs()
    inp.metadata["purpose"] = "recovery"
    inp.metadata["expected_challenge"]["dynamic"].update(
        version=2,
        head_start_at_ms=12000,
        head_duration_ms=12000,
        head_turns=["left", "right", "center"],
        head_mode="adaptive",
        head_timeout_ms=18000,
    )
    return inp


@pytest.fixture
def forbid_frame_work(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A failed head check must stop before frame selection or backend inference")

    monkeypatch.setattr(selection, "video_sha256", lambda _: "a" * 64)
    monkeypatch.setattr(selection, "select_video_frames", forbidden)
    return forbidden


@pytest.mark.parametrize(
    "status,code,gate,expected_status,expected_code",
    [
        (Status.ERROR, ErrorCode.E_TIMEOUT, Gate.UNCLEAR, Status.ERROR, ErrorCode.E_TIMEOUT),
        (Status.ERROR, ErrorCode.E_INTERNAL, Gate.UNCLEAR, Status.ERROR, ErrorCode.E_INTERNAL),
        (Status.ERROR, ErrorCode.E_DECODE, Gate.PASS, Status.ERROR, ErrorCode.E_DECODE),
        (Status.DEGRADED, ErrorCode.E_DECODE, Gate.UNCLEAR, Status.DEGRADED, ErrorCode.E_DECODE),
        (
            Status.NOT_APPLICABLE,
            ErrorCode.E_NO_FACE,
            Gate.UNCLEAR,
            Status.NOT_APPLICABLE,
            ErrorCode.E_NO_FACE,
        ),
        (Status.ERROR, None, Gate.UNCLEAR, Status.ERROR, ErrorCode.E_INTERNAL),
        (Status.OK, ErrorCode.E_TIMEOUT, Gate.PASS, Status.ERROR, ErrorCode.E_TIMEOUT),
        (Status.OK, ErrorCode.E_INTERNAL, Gate.FAIL, Status.ERROR, ErrorCode.E_INTERNAL),
        (Status.OK, None, Gate.FAIL, Status.DEGRADED, ErrorCode.E_LOW_QUALITY),
        (Status.OK, None, Gate.UNCLEAR, Status.DEGRADED, ErrorCode.E_LOW_QUALITY),
        (Status.DEGRADED, None, Gate.UNCLEAR, Status.DEGRADED, ErrorCode.E_LOW_QUALITY),
        (Status.NOT_APPLICABLE, None, Gate.UNCLEAR, Status.DEGRADED, ErrorCode.E_LOW_QUALITY),
    ],
)
def test_nested_head_failure_preserves_error_before_motion_fallback(
    monkeypatch,
    adaptive_input,
    forbid_frame_work,
    status,
    code,
    gate,
    expected_status,
    expected_code,
):
    head = ModuleResult(
        module="head_turn",
        model_version="synthetic",
        status=status,
        error_code=code,
        gate=gate,
        evidence=[
            Evidence(
                type="scalar",
                name="view_times_ms",
                value={"front": 250, "left": 13000, "right": 15000},
            )
        ],
        latency_ms=0,
    )
    monkeypatch.setattr(
        selection, "HeadTurnDetector", lambda *_: SimpleNamespace(predict=lambda _: head)
    )
    with pytest.raises(LandmarkError) as caught:
        selection.session_views(adaptive_input, SimpleNamespace(observe=forbid_frame_work))
    assert (caught.value.status, caught.value.code) == (expected_status, expected_code)


@pytest.mark.parametrize("module", ["face_pad", "face_deepfake"])
@pytest.mark.parametrize(
    "failure,expected_status,expected_code",
    [
        (LandmarkError(ErrorCode.E_TIMEOUT), Status.ERROR, ErrorCode.E_TIMEOUT),
        (RuntimeError("synthetic reader failure"), Status.ERROR, ErrorCode.E_INTERNAL),
        (
            LandmarkError(ErrorCode.E_DECODE, Status.DEGRADED),
            Status.DEGRADED,
            ErrorCode.E_DECODE,
        ),
    ],
)
def test_session_attack_preserves_real_head_reader_error_without_scores(
    adaptive_input, forbid_frame_work, module, failure, expected_status, expected_code
):
    def extract(*args, **kwargs):
        raise failure

    reader = SimpleNamespace(extract=extract, observe=forbid_frame_work)
    backend = SimpleNamespace(
        name=module, frames_version="synthetic", predict_frames=forbid_frame_work
    )
    detector = SessionAttackDetector(backend, reader, manual_demo=ManualDemoThresholds())
    result = detector.predict(adaptive_input)
    assert (result.status, result.error_code) == (expected_status, expected_code)
    assert result.module == module
    assert result.gate == Gate.UNCLEAR
    assert result.score is None and result.prob_attack is None
    assert not result.is_usable
    assert result.quality == {} and result.evidence == []
