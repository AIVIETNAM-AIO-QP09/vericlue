"""Mọi mock, ở mọi kịch bản, trả ModuleResult hợp lệ với hợp đồng JSON."""

import json
from pathlib import Path

import jsonschema
import pytest

from vericlue_ml.common import Detector, DetectorInput, Module, Status
from vericlue_ml.mock import MOCK_DETECTORS, SCENARIOS
from vericlue_ml.registry import get_detector

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "packages/contracts/schemas/module_result.schema.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("module", list(Module), ids=lambda m: m.value)
def test_every_mock_matches_contract(module, scenario):
    result = MOCK_DETECTORS[module].predict(DetectorInput(metadata={"scenario": scenario}))
    jsonschema.validate(result.to_contract(), SCHEMA)
    assert result.module == module.value


def test_error_scenario_is_never_usable():
    for det in MOCK_DETECTORS.values():
        r = det.predict(DetectorInput(metadata={"scenario": "error"}))
        assert r.status == Status.ERROR
        assert r.error_code == "E_INTERNAL"
        assert not r.is_usable


def test_degraded_is_not_usable():
    r = MOCK_DETECTORS[Module.FACE_PAD].predict(DetectorInput(metadata={"scenario": "low_quality"}))
    assert r.status == Status.DEGRADED
    assert not r.is_usable


def test_default_scenario_is_genuine():
    r = MOCK_DETECTORS[Module.FACE_DEEPFAKE].predict(DetectorInput())
    assert r.is_usable and r.prob_attack < 0.1


def test_unknown_scenario_raises():
    with pytest.raises(ValueError):
        MOCK_DETECTORS[Module.FACE_PAD].predict(DetectorInput(metadata={"scenario": "abc"}))


def test_mocks_are_deterministic_and_independent():
    det = MOCK_DETECTORS[Module.CHROMAPULSE]
    a = det.predict(DetectorInput(metadata={"scenario": "faceswap"}))
    a.evidence.clear()  # sửa kết quả trả về không được làm hỏng bảng kịch bản
    b = det.predict(DetectorInput(metadata={"scenario": "faceswap"}))
    assert b.evidence and b.gate == "fail"


@pytest.mark.parametrize(
    ("scenario", "module", "expect_gate"),
    [
        ("print", Module.CHROMAPULSE, "fail"),
        ("replay", Module.CHROMAPULSE, "fail"),
        ("virtual_cam", Module.CAMPROBE, "fail"),
        ("faceswap", Module.CHROMAPULSE, "fail"),
        ("low_quality", Module.QUALITY, "fail"),
        ("low_quality", Module.CHROMAPULSE, "unclear"),
        ("genuine", Module.CAMPROBE, "pass"),
    ],
)
def test_scenarios_drive_expected_gates(scenario, module, expect_gate):
    r = MOCK_DETECTORS[module].predict(DetectorInput(metadata={"scenario": scenario}))
    assert r.gate == expect_gate


def test_registry_returns_mock_and_satisfies_protocol(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "true")
    det = get_detector("face_pad")
    assert isinstance(det, Detector)
    assert det.version.startswith("mock@")


def test_registry_real_model_not_ready_points_to_task(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "false")
    with pytest.raises(NotImplementedError, match="PRES-02"):
        get_detector(Module.CHROMAPULSE)
