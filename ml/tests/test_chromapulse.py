"""Synthetic correspondence and safety tests, not a face/attack accuracy benchmark."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from jsonschema import validate

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Gate, Status
from vericlue_ml.presence.chromapulse import (
    ChromaPulseDetector,
    evaluate_colors,
    log_linear,
    parse_plan,
)
from vericlue_ml.presence.color_regions import (
    REGION_LANDMARKS,
    ColorObservation,
    RegionStat,
    color_observation,
    summarize_pixels,
)
from vericlue_ml.presence.landmarks import LandmarkError
from vericlue_ml.registry import get_chromapulse_diagnostic, get_detector

PALETTE = ("#ffcc73", "#73d9ff", "#ffb3eb", "#80e09e")


def inputs(video=Path("unused.mp4")):
    return DetectorInput(
        session_id="ses_synthetic",
        video=video,
        metadata={
            "challenge_id": "ch_synthetic",
            "expected_challenge": {
                "challenge_id": "ch_synthetic",
                "baseline_ms": 1000,
                "color_sequence": [
                    {"rgb": PALETTE[i], "hold_ms": 500, "transition_ms": 150}
                    for i in (0, 1, 0, 2, 3, 1, 3, 2)
                ],
                "dynamic": {
                    "version": 1,
                    "session_id": "ses_synthetic",
                    "gaze_points": [{"at_ms": 6200}],
                },
            },
        },
    )


def inverse_log(value):
    linear = np.exp(value)
    return np.where(linear <= 0.0031308, 12.92 * linear, 1.055 * linear ** (1 / 2.4) - 0.055) * 255


def stat(rgb):
    return RegionStat(tuple(rgb), tuple(rgb), 100, 0.0)


def matching(lag=100, plan=None):
    plan = plan or parse_plan(inputs())
    times = np.arange(0, plan.ends[-1], 100)
    target = log_linear(plan.rgb_at(times - lag))
    rows = []
    for time, x in zip(times, target, strict=True):
        regions = {
            name: stat(inverse_log(log_linear(np.array([110, 115, 120])) + x * 0.08 + i * 0.01))
            for i, name in enumerate(REGION_LANDMARKS)
        }
        regions["background"] = stat((100, 100, 100))
        rows.append(ColorObservation(float(time), 1, regions))
    return rows


def test_known_lag_is_apparent_and_never_reported_as_verified_physical_latency():
    result = evaluate_colors(matching(), parse_plan(inputs()))
    assert result.metrics["fit_r2_in_sample"] == pytest.approx(1)
    assert result.metrics["apparent_lag_ms"] == 100
    assert result.metrics["timing_verified"] is False
    assert result.metrics["calibrated"] is False
    assert result.metrics["sampling_interval_ms"] == 100
    assert result.reason == "uncalibrated_timing_unverified"
    assert result.series and np.isfinite(result.metrics["design_condition_number"])


def test_different_temporal_sequence_reduces_fit():
    inp = inputs()
    sequence = inp.metadata["expected_challenge"]["color_sequence"]
    for step, index in zip(sequence, (0, 3, 1, 0, 2, 1, 3, 2), strict=True):
        step["rgb"] = PALETTE[index]
    result = evaluate_colors(matching(plan=parse_plan(inp)), parse_plan(inputs()))
    assert result.metrics["fit_r2_in_sample"] < 0.9


def test_rank_deficient_challenge_is_not_fit():
    plan = parse_plan(inputs())
    plan = replace(
        plan, colors=tuple((100, 100, 100) if i % 2 else (150, 150, 150) for i in range(8))
    )
    result = evaluate_colors(matching(plan=plan), plan)
    assert result.reason == "insufficient_color_excitation"


@pytest.mark.parametrize("kind", ["flat", "background_only"])
def test_no_differential_response_is_unobservable(kind):
    rows = matching()
    for i, row in enumerate(rows):
        value = (100 + i % 20,) * 3 if kind == "background_only" else (110,) * 3
        regions = {name: stat(value) for name in (*REGION_LANDMARKS, "background")}
        rows[i] = replace(row, regions=regions)
    result = evaluate_colors(rows, parse_plan(inputs()))
    assert result.reason == "unobservable_response"
    assert "fit_r2_in_sample" not in result.metrics


@pytest.mark.parametrize(
    "kind",
    ["short", "gap", "clipped", "missing_region", "nonfinite", "duplicate", "multi", "no_face"],
)
def test_unusable_measurements_do_not_produce_a_fit(kind):
    rows = matching()
    if kind == "short":
        rows = rows[:20]
    elif kind == "gap":
        rows = rows[:30] + rows[34:]
    elif kind == "duplicate":
        rows[30] = replace(rows[30], at_ms=rows[29].at_ms)
    elif kind in ("multi", "no_face"):
        rows = [replace(row, face_count=2 if kind == "multi" else 0) for row in rows]
    else:
        for row in rows:
            if kind == "missing_region":
                del row.regions["nose"]
            elif kind == "clipped":
                row.regions["nose"] = RegionStat((255, 255, 255), None, 100, 1.0)
            else:
                row.regions["nose"] = stat((float("nan"), 100, 100))
    result = evaluate_colors(rows, parse_plan(inputs()))
    assert "fit_r2_in_sample" not in result.metrics
    assert not result.series


@pytest.mark.parametrize("kind", ["session", "attempt", "version", "timing", "bool", "rgb", "hold"])
def test_invalid_or_unbound_server_plan_rejected(kind):
    inp = inputs()
    challenge = inp.metadata["expected_challenge"]
    if kind == "session":
        inp.session_id = "other"
    elif kind == "attempt":
        inp.metadata["challenge_id"] = "other"
    elif kind == "version":
        challenge["dynamic"]["version"] = 2
    elif kind == "timing":
        challenge["dynamic"]["gaze_points"][0]["at_ms"] += 1
    elif kind == "bool":
        challenge["baseline_ms"] = True
    else:
        challenge["color_sequence"][0]["rgb" if kind == "rgb" else "hold_ms"] = (
            "invalid" if kind == "rgb" else 10000
        )
    with pytest.raises(LandmarkError):
        parse_plan(inp)


def test_srgb_timeline_matches_transition_before_hold():
    plan = parse_plan(inputs())
    samples = plan.rgb_at(np.array([0, 1000, 1075, 1150, 1649, 1650]))
    assert samples[0].tolist() == [209] * 3
    assert samples[1].tolist() == [209] * 3
    assert samples[2].tolist() == [232, 207, 162]
    assert samples[3].tolist() == [255, 204, 115]
    assert np.array_equal(samples[3], samples[4])
    assert np.array_equal(samples[4], samples[5])


def test_luma_trim_is_not_a_per_channel_clip_and_uses_medians():
    result = summarize_pixels(np.array([[55] * 3, [200] * 3, [100, 80, 60], [255, 50, 50]]))
    assert result.pixels == 4 and result.excluded_fraction == 0.5
    assert result.rgb_trim == (177.5, 65.0, 55.0)
    assert summarize_pixels(np.empty((0, 3))).rgb_trim is None


def fake_face():
    points = [SimpleNamespace(x=0.5, y=0.5) for _ in range(478)]
    for indices in REGION_LANDMARKS.values():
        for j, index in enumerate(indices):
            points[index] = SimpleNamespace(x=0.4 + (j % 2) * 0.2, y=0.3 + (j // 2) * 0.1)
    return SimpleNamespace(face_landmarks=[points])


def test_region_extraction_keeps_five_regions_background_and_no_pixels():
    rgb = np.full((100, 100, 3), 100, dtype=np.uint8)
    row = color_observation(fake_face(), rgb, 1500)
    assert row.face_count == 1 and row.at_ms == 1500
    assert set(row.regions) == {*REGION_LANDMARKS, "background"}
    assert all(stat.rgb_trim == (100, 100, 100) for stat in row.regions.values())
    assert row.regions["background"].pixels == 2 * 12 * 12
    result = fake_face()
    result.face_landmarks *= 2
    assert color_observation(result, rgb, 1500).regions == {}


def test_background_overlapping_face_guard_is_not_measured():
    result = fake_face()
    result.face_landmarks[0][0] = SimpleNamespace(x=0.0, y=0.0)
    result.face_landmarks[0][1] = SimpleNamespace(x=1.0, y=0.8)
    row = color_observation(result, np.full((100, 100, 3), 100, dtype=np.uint8), 1000)
    assert row.regions["background"].pixels == 0


def test_detector_ignores_client_measurements_and_stays_unclear(tmp_path):
    video = tmp_path / "synthetic.mp4"
    video.write_bytes(b"synthetic injected-reader bytes")

    class Reader:
        def extract(self, path, **kwargs):
            assert path == video and kwargs == {"start_ms": 0, "end_ms": 6200}
            return matching()

    detector = ChromaPulseDetector(Reader())
    inp = inputs(video)
    inp.signals = {"region_means": "fabricated", "color_events": [{"at_ms": -999999}]}
    result = detector.predict(inp)
    assert result.status == Status.DEGRADED and result.gate == Gate.UNCLEAR
    assert not result.is_usable and result.prob_attack is None and result.score is None
    assert result.quality["fit_r2_in_sample"] == pytest.approx(1)
    assert result.quality["client_measurements_used"] is False
    assert result.to_contract()["module"] == "chromapulse"
    schema = (
        Path(__file__).resolve().parents[2] / "packages/contracts/schemas/module_result.schema.json"
    )
    validate(result.to_contract(), json.loads(schema.read_text(encoding="utf-8")))


def test_changed_source_and_native_failure_cannot_pass(tmp_path):
    path = tmp_path / "synthetic.mp4"
    path.write_bytes(b"before")

    class Reader:
        def extract(self, *_args, **_kwargs):
            path.write_bytes(b"after")
            return matching()

    result = ChromaPulseDetector(Reader()).predict(inputs(path))
    assert result.status == Status.ERROR and result.error_code == ErrorCode.E_INTEGRITY
    assert result.gate == Gate.UNCLEAR

    class BrokenReader:
        def extract(self, *_args, **_kwargs):
            raise RuntimeError("backend unavailable")

    result = ChromaPulseDetector(BrokenReader()).predict(inputs(path))
    assert result.status == Status.ERROR and result.gate == Gate.UNCLEAR


def test_explicit_factory_preserves_default_registry_behavior():
    detector = get_chromapulse_diagnostic()
    assert isinstance(detector, ChromaPulseDetector)
    assert get_chromapulse_diagnostic() is detector
    assert get_chromapulse_diagnostic(mock=True) is get_detector("chromapulse", mock=True)
    assert get_detector("chromapulse", mock="mixed").version.startswith("mock@")
    with pytest.raises(NotImplementedError):
        get_detector("chromapulse", mock=False)
