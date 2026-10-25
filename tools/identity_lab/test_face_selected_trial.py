import face_selected_trial as module
import pytest


def report():
    from face_robustness import SCENARIOS

    models = {}
    for name, latency in [("adaface_ir18", 50), ("adaface_ir101", 300)]:
        models[name] = {
            "embedding_ms_median": latency,
            "scenarios": {
                s: {"validation_operating_point": {"fmr_scored": 0.0, "fnmr_scored": 0.0}}
                for s in SCENARIOS
            },
        }
    return {
        "models": models,
        "selected": "adaface_ir18",
        "protocol": {"code_sha256": "valid"},
        "alignment_code_sha256": "valid",
        "runtime": {"numpy": "expected"},
    }


def test_selection_rejects_manual_model_switch(monkeypatch):
    monkeypatch.setattr(module, "sha", lambda p: "valid")
    monkeypatch.setattr(module, "version", lambda n: "expected")
    value = report()
    assert module.verify_selection(value) == "adaface_ir18"
    value["selected"] = "adaface_ir101"
    with pytest.raises(ValueError, match="policy"):
        module.verify_selection(value)


def test_selection_checks_implementation_and_runtime(monkeypatch):
    monkeypatch.setattr(module, "sha", lambda p: "changed")
    with pytest.raises(ValueError, match="code changed"):
        module.verify_selection(report())
    monkeypatch.setattr(module, "sha", lambda p: "valid")
    monkeypatch.setattr(module, "version", lambda n: "changed")
    with pytest.raises(ValueError, match="Runtime"):
        module.verify_selection(report())
