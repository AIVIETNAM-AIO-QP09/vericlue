"""Parity must fail closed even when captures are missing or internally inconsistent."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "parity_gend.py"


@pytest.fixture
def tool():
    assert SCRIPT.is_file(), "Portable parity tool is not implemented"
    spec = importlib.util.spec_from_file_location("gend_parity_tool", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def captures():
    values = {"input": np.zeros((9, 3, 224, 224), dtype=np.float32)}
    for count in (1, 2, 9):
        normalized = np.zeros((count, 1024), dtype=np.float32)
        normalized[:, 0] = 1
        values.update(
            {
                f"{count}_pooled": normalized.copy(),
                f"{count}_normalized": normalized,
                f"{count}_logits": np.tile([0, np.log(3)], (count, 1)),
                f"{count}_probabilities": np.tile([0.25, 0.75], (count, 1)),
                f"{count}_p_fake": np.full(count, 0.75),
            }
        )
    return values


def test_complete_consistent_captures_pass(tool):
    report = tool.compare_arrays(captures(), captures())
    assert report["status"] == "PASS"
    assert len(report["checks"]) == 15


@pytest.mark.parametrize("fault", ["nonfinite", "shape", "missing", "polarity", "extra"])
def test_invalid_capture_cannot_pass(tool, fault):
    candidate = captures()
    if fault == "nonfinite":
        candidate["1_logits"][0, 0] = np.nan
    elif fault == "shape":
        candidate["1_logits"] = np.zeros((1, 1))
    elif fault == "missing":
        del candidate["9_normalized"]
    elif fault == "polarity":
        candidate["2_p_fake"][:] = 0.25
    else:
        candidate["extra"] = np.zeros(1)
    report = tool.compare_arrays(captures(), candidate)
    assert report["status"] != "PASS"
    json.dumps(report, allow_nan=False)


def test_identical_wrong_polarity_cannot_pass(tool):
    values = captures()
    values["1_p_fake"][:] = 0.25
    assert tool.compare_arrays(values, values)["status"] == "FAIL"


def test_finite_numeric_mismatch_is_fail(tool):
    candidate = captures()
    candidate["2_pooled"] += 0.01
    assert tool.compare_arrays(captures(), candidate)["status"] == "FAIL"


def test_missing_reference_retains_error_report(tool, tmp_path):
    code = tool.main(
        [
            "--mode",
            "compare",
            "--models-dir",
            str(tmp_path),
            "--upstream-dir",
            str(tmp_path),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert code == 2
    assert report["status"] == "UNVERIFIED"
    assert report["error_type"] == "FileNotFoundError"


def test_hash_mismatch_rejected_before_importing_reference(tool, tmp_path):
    for name in tool.EXPECTED:
        (tmp_path / name).write_text("unreviewed source")
    with pytest.raises(ValueError, match="Hash mismatch"):
        tool.verify_upstream(tmp_path)


def test_missing_upstream_rejected(tool, tmp_path):
    with pytest.raises(FileNotFoundError):
        tool.verify_upstream(tmp_path)


def test_run_refuses_to_overwrite_previous_evidence(tool, tmp_path):
    old = '{"status": "PASS", "old_evidence": true}'
    (tmp_path / "report.json").write_text(old)
    code = tool.main(
        [
            "--models-dir",
            str(tmp_path / "models"),
            "--upstream-dir",
            str(tmp_path / "source"),
            "--out",
            str(tmp_path),
        ]
    )
    assert code == 2
    assert (tmp_path / "report.json").read_text() == old


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "missing_metrics",
        "missing_metadata",
        "changed_identity",
        "strict_load",
        "pixel_missing",
        "pixel_nonfinite",
        "pixel_false_pass",
        "pixel_shape",
        "align_inventory",
        "processor_sizes",
        "boolean",
        "negative",
    ],
)
def test_saved_evidence_requires_complete_measurements(tool, tmp_path, monkeypatch, fault):
    # The file/model hashing boundary is replaced; report parsing and guards remain real.
    identity = {
        "models": [],
        "repo_commit": "test",
        "wrapper_sha256": "test",
        "upstream_source_sha256": {},
        "runtime_identity": {},
        "harness_sha256": "test",
        "manifest_sha256": "test",
        "wrapper_model_version": "test",
        "upstream_commit": "test",
        "repo_dirty": True,
        "support_source_sha256": {},
    }
    monkeypatch.setattr(tool, "provenance", lambda args: identity)
    metadata = {
        **identity,
        "runtime": {},
        "post_run_provenance_match": True,
        "sample_count": 9,
        "inference_batch_sizes": [1, 2, 9],
        "class_index": {"0": "real", "1": "fake"},
        "checkpoint": {"tensor_count": 394, "missing": [], "unexpected": []},
    }
    if fault == "missing_metadata":
        del metadata["runtime"]
    elif fault == "strict_load":
        metadata["checkpoint"]["missing"] = ["weight"]
    pre = {
        "provenance": identity,
        "post_run_provenance_match": True,
        "sample_count": 6,
        "alignment_sample_count": 6,
        "status": "pass",
        "checks": [
            {"size": size, "max_absolute_error": 0, "pass": True}
            for size in (31, 224, 225, 640, 73, 112)
        ],
        "alignment": [
            {
                "angle": angle,
                "landmark_scale": scale,
                "shift": shift,
                "shape": [64, 64, 3],
                "max_pixel_error": 0,
                "pass": True,
            }
            for angle, scale, shift in [
                (0, 1, [0, 0]),
                (17, 1, [30, 10]),
                (-23, 0.6, [-10, 40]),
                (41, 1.4, [90, -25]),
                (-8, 0.21, [-140, -140]),
                (3, 2, [300, 100]),
            ]
        ],
    }
    if fault == "missing_metrics":
        pre["checks"] = []
    elif fault == "pixel_missing":
        del pre["alignment"][0]["max_pixel_error"]
    elif fault == "pixel_nonfinite":
        pre["alignment"][0]["max_pixel_error"] = "NaN"
    elif fault == "pixel_false_pass":
        pre["alignment"][0]["max_pixel_error"] = 3
    elif fault == "pixel_shape":
        pre["alignment"][0]["shape"] = [0, 0, 3]
    elif fault == "align_inventory":
        pre["alignment"][0]["angle"] = 999
    elif fault == "processor_sizes":
        pre["checks"][0]["size"] = 224
    elif fault == "boolean":
        pre["checks"][0]["pass"] = "yes"
    elif fault == "negative":
        pre["checks"][0]["max_absolute_error"] = -1
    for backend in ("upstream", "wrapper"):
        np.savez(tmp_path / f"{backend}.npz", **captures())
        tool.write(tmp_path / f"{backend}.json", metadata)
    if fault == "changed_identity":
        metadata["repo_commit"] = "other"
        tool.write(tmp_path / "wrapper.json", metadata)
    tool.write(tmp_path / "preprocessing.json", pre)
    code = tool.main(
        [
            "--mode",
            "compare",
            "--models-dir",
            str(tmp_path),
            "--upstream-dir",
            str(tmp_path),
            "--out",
            str(tmp_path),
        ]
    )
    report = json.loads((tmp_path / "report.json").read_text())
    if fault is None:
        assert code == 0
        assert report["status"] == "PASS"
    elif fault == "pixel_false_pass":
        assert code == 1
        assert report["status"] == "FAIL"
    else:
        assert code == 2
        assert report["status"] == "UNVERIFIED"
        assert report["error"]
