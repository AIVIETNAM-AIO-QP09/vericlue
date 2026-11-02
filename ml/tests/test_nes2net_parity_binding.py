"""Parity binds a measured software runtime; it never authorizes a voice decision."""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from vericlue_ml.voice import nes2net
from vericlue_ml.voice.nes2net import Nes2NetBackend, Nes2NetDetector

SUMMARY = (
    Path(__file__).resolve().parents[2] / "docs/status/results/VOICE-09-parity-2026-11-01.json"
)


@pytest.fixture
def binding(tmp_path, monkeypatch):
    report = json.loads(SUMMARY.read_text(encoding="utf-8"))
    source = tmp_path / "parity.json"
    source.write_text(json.dumps(report), encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setenv("NES2NET_PARITY_REPORT", str(source))
    monkeypatch.setenv("NES2NET_PARITY_SHA256", digest)
    return report, source, digest


def runtime(report):
    values = report["windows_runtime"]
    return {
        "system": "Windows",
        "python": values["python"].split()[0],
        **{k: values[k] for k in ("torch", "transformers", "numpy", "cpu_threads")},
    }


def test_reviewed_parity_report_keeps_its_measured_byte_identity():
    from vericlue_ml.voice.nes2net_parity import verify_parity

    # Existing native measurements bind these exact bytes, including line endings.
    digest = "669bf62e4db134a46e8a0dd8f3d5b6a72bba90a984c3a7901fa8e866e8f21a48"
    assert hashlib.sha256(SUMMARY.read_bytes()).hexdigest() == digest
    report = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert verify_parity(SUMMARY, digest, report["checkpoint_sha256"], runtime(report)) == digest


def test_only_exact_runtime_and_checkpoint_can_use_pinned_report(binding):
    from vericlue_ml.voice.nes2net_parity import verify_parity

    report, source, digest = binding
    assert verify_parity(source, digest, report["checkpoint_sha256"], runtime(report)) == digest
    for key, changed in (("torch", "2.8.0"), ("cpu_threads", 1), ("python", "3.12.3")):
        with pytest.raises(ValueError):
            verify_parity(
                source, digest, report["checkpoint_sha256"], runtime(report) | {key: changed}
            )
    with pytest.raises(ValueError):
        verify_parity(source, digest, "0" * 64, runtime(report))
    source.write_text(source.read_text() + " ")
    with pytest.raises(ValueError):
        verify_parity(source, digest, report["checkpoint_sha256"], runtime(report))


@pytest.mark.parametrize("fault", ["synthetic", "duplicates", "margin", "count", "version", "sign"])
def test_failed_or_inadequate_evidence_is_never_verified(binding, fault):
    from vericlue_ml.voice.nes2net_parity import verify_parity

    report, source, _ = binding
    bad = copy.deepcopy(report)
    comparison = bad["windows_comparison"]
    if fault == "synthetic":
        comparison["synthetic"] = True
    elif fault == "duplicates":
        comparison["diversity"]["unique_window_count"] = 31
    elif fault == "margin":
        comparison["max_abs_margin_diff"] = 0.001
    elif fault == "count":
        comparison["independent_sample_count"] = 31
    elif fault == "version":
        bad["model_version"] = "another-model"
    else:
        comparison["sign_agreement"] = 0.99
    source.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_parity(
            source,
            hashlib.sha256(source.read_bytes()).hexdigest(),
            report["checkpoint_sha256"],
            runtime(report),
        )


def test_explicit_but_incomplete_binding_fails_at_construction(monkeypatch):
    monkeypatch.setenv("NES2NET_PARITY_REPORT", "missing.json")
    monkeypatch.delenv("NES2NET_PARITY_SHA256", raising=False)
    with pytest.raises(ValueError):
        Nes2NetBackend()


def test_verified_parity_does_not_change_diagnostic_status_or_probability(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(nes2net, "speech_bounds", lambda x: (0, len(x)))
    backend = SimpleNamespace(logits=lambda _: [0.1, 2], parity_sha256="a" * 64)
    result = Nes2NetDetector(backend=backend).predict_samples(np.full(64000, 0.1, np.float32))
    assert result.quality["frontend_parity_verified"] is True
    assert result.quality["parity_report_sha256"] == "a" * 64
    assert result.status == "degraded" and result.gate == "unclear"
    assert result.prob_attack is None and not result.is_usable


def test_backend_rechecks_runtime_and_revokes_claim_after_runtime_changes(binding, monkeypatch):
    from vericlue_ml.voice import nes2net_parity

    report, source, digest = binding
    live = runtime(report)
    monkeypatch.setattr(nes2net_parity, "runtime_identity", lambda: live)
    backend = Nes2NetBackend()
    monkeypatch.setattr(backend, "_checkpoint", lambda: source)
    monkeypatch.setattr(backend, "_load_native", lambda _: object())
    backend.preload()
    assert backend.parity_sha256 == digest
    live["cpu_threads"] = 1
    with pytest.raises(ValueError):
        backend.preload()
    assert backend.parity_sha256 is None


def test_parity_survives_timeline_and_ipc_but_still_never_passes(monkeypatch):
    import io
    from types import SimpleNamespace

    from vericlue_ml.eval.nes2net_client import validate_reply
    from vericlue_ml.eval.nes2net_worker import serve
    from vericlue_ml.eval.voice_wire import encode_request
    from vericlue_ml.voice.nes2net_timeline import Nes2NetTimelineDetector, validate_timeline

    monkeypatch.setattr(nes2net, "speech_bounds", lambda x: (0, len(x)))
    backend = SimpleNamespace(
        logits=lambda _: [0.1, 2],
        parity_sha256="a" * 64,
        config={"revision": nes2net.REVISION, "checkpoint": "checkpoint.pth", "sha256": "b" * 64},
        model_hashes={"checkpoint.pth": "b" * 64},
        load_report={},
        _model=object(),
    )
    detector = Nes2NetTimelineDetector(backend=backend)
    samples = np.full(128000, 0.1, np.float32)
    result = detector.predict_samples(samples)
    assert result.quality["frontend_parity_verified"] is True
    assert result.quality["parity_report_sha256"] == "a" * 64
    validate_timeline(result, len(samples))
    frame, checksum = encode_request(samples, "a" * 32)
    target = io.BytesIO()
    serve(io.BytesIO(frame), target, detector)
    reply = validate_reply(
        target.getvalue(),
        "a" * 32,
        checksum,
        expected_version=detector.version,
        sample_count=len(samples),
    )
    assert reply["frontend_parity_verified"] is True
    assert reply["result"]["status"] == "degraded"
    assert reply["calibrated"] is False and reply["result"]["gate"] == "unclear"


@pytest.mark.parametrize(
    "field,value",
    [("samples", 0), ("independent_pcm_windows", 0), ("speakers", True)],
)
def test_summary_claims_must_match_measured_population(binding, field, value):
    from vericlue_ml.voice.nes2net_parity import verify_parity

    report, source, _ = binding
    report[field] = value
    source.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_parity(
            source,
            hashlib.sha256(source.read_bytes()).hexdigest(),
            report["checkpoint_sha256"],
            runtime(report),
        )


@pytest.mark.parametrize(
    "field,value",
    [("sign_agreement", True), ("independent_sample_count", 32.0), ("window_count", True)],
)
def test_comparison_rejects_coerced_numeric_claims(binding, field, value):
    from vericlue_ml.voice.nes2net_parity import verify_parity

    report, source, _ = binding
    report["windows_comparison"][field] = value
    source.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_parity(
            source,
            hashlib.sha256(source.read_bytes()).hexdigest(),
            report["checkpoint_sha256"],
            runtime(report),
        )


def test_changed_shape_compatible_graph_cannot_inherit_parity(binding):
    from vericlue_ml.voice.nes2net_parity import verify_parity

    report, source, digest = binding
    config = copy.deepcopy(Nes2NetBackend().config)
    config["backbone"]["layer_norm_eps"] = 0.01
    with pytest.raises(ValueError):
        verify_parity(source, digest, report["checkpoint_sha256"], runtime(report), config=config)


@pytest.mark.parametrize("fault", ["numeric_marker", "nonhex", "calibrated", "error"])
def test_ipc_rejects_malformed_or_unmeasured_parity(monkeypatch, fault):
    import io
    from types import SimpleNamespace

    from vericlue_ml.eval.nes2net_client import validate_reply
    from vericlue_ml.eval.nes2net_worker import serve
    from vericlue_ml.eval.voice_wire import encode_request

    monkeypatch.setattr(nes2net, "speech_bounds", lambda x: (0, len(x)))
    backend = SimpleNamespace(
        logits=lambda _: [0.1, 2],
        parity_sha256="a" * 64,
        config={"revision": nes2net.REVISION, "checkpoint": "unit", "sha256": "b" * 64},
        model_hashes={},
        load_report={},
        _model=object(),
    )

    frame, checksum = encode_request(np.full(64000, 0.1, np.float32), "a" * 32)
    target = io.BytesIO()
    serve(io.BytesIO(frame), target, Nes2NetDetector(backend=backend))
    body = json.loads(target.getvalue())
    quality = body["result"]["quality"]
    if fault == "numeric_marker":
        quality["frontend_parity_verified"] = 1.0
    elif fault == "nonhex":
        quality["parity_report_sha256"] = "z" * 64
    elif fault == "calibrated":
        quality["calibrated"] = True
    else:
        body["result"].update(status="error", error_code="E_INTERNAL", score=None)
    with pytest.raises(ValueError):
        validate_reply((json.dumps(body) + "\n").encode(), "a" * 32, checksum)


@pytest.mark.parametrize("field", ["source_commit", "script_sha256", "implementation_binding"])
def test_unmeasured_source_and_implementation_cannot_inherit_parity(binding, field):
    from vericlue_ml.voice.nes2net_parity import verify_parity

    report, source, _ = binding
    report[field] = {} if field == "implementation_binding" else "0" * len(report[field])
    source.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_parity(
            source,
            hashlib.sha256(source.read_bytes()).hexdigest(),
            report["checkpoint_sha256"],
            runtime(report),
        )
