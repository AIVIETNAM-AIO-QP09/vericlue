"""Synthetic candidate artifacts exercise offline safety, never deployment evidence."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_ltt import protocol
from test_nes2net_readiness import report_fixture, sample

from vericlue_ml.common import calibration
from vericlue_ml.eval import nes2net_utterance as utterance

RUNTIME = {
    "system": "Windows",
    "python": "3.12.10",
    "torch": "2.7.1",
    "transformers": "4.51.3",
    "numpy": "2.2.6",
    "cpu_threads": 2,
}


def write(path, body):
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def fixture(tmp_path, monkeypatch, *, n=100, failed=()):
    samples = [sample(i, i % 2) for i in range(8)]
    samples += [sample(100 + i, 1, split="calib_ltt") for i in range(n)]
    samples += [sample(1000, 0, split="calib_ltt")]
    samples += [sample(2000 + i, i % 2, split="test") for i in range(4)]
    path, body = report_fixture(tmp_path, monkeypatch, samples, failed=failed)
    body["runtime"] = dict(RUNTIME)
    write(path, body)
    monkeypatch.setattr(utterance, "fit", calibration.fit)
    fit_path = tmp_path / "fit.json"
    utterance.fit_report(path, fit_path)
    declared = protocol(grid=[[0.25], [0.75]], expected_attack_types=["tts"])
    protocol_path = write(tmp_path / "protocol.json", declared)
    return path, fit_path, protocol_path, body


def test_score_preserves_degraded_originals_and_uses_frozen_calibrator(tmp_path, monkeypatch):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, _, body = fixture(tmp_path, monkeypatch)
    original = report.read_bytes()

    def forbidden(*args, **kwargs):
        pytest.fail("Candidate scoring must never refit")

    monkeypatch.setattr(calibration, "fit", forbidden)
    monkeypatch.setattr(utterance, "fit", forbidden)
    result = candidate.score_report(
        report, fit, report, tmp_path / "scores.json", split="calib_ltt"
    )
    assert result["sample_count"] == 101
    assert len(result["rows"]) == 101
    assert all(0 < row["candidate_probability"] < 1 for row in result["rows"])
    assert all(row["module_result"]["status"] == "degraded" for row in result["rows"])
    assert all(row["module_result"].get("prob_attack") is None for row in result["rows"])
    assert result["diagnostic_only"] is True
    assert result["deployed"] is False and result["runtime_eligible"] is False
    assert result["binding"]["runtime"] == RUNTIME
    assert result["measurement_report_sha256"] == hashlib.sha256(original).hexdigest()
    assert report.read_bytes() == original
    assert result["dataset"] == body["dataset"]


def test_synthetic_locked_selection_then_test_evaluation(tmp_path, monkeypatch):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, protocol_path, _ = fixture(tmp_path, monkeypatch)
    lock_path = tmp_path / "selected.json"
    selected = candidate.select_report(report, fit, report, protocol_path, lock_path)
    assert selected["selected"]["parameters"] == [0.25]
    assert selected["ltt_outcome"]["fixture_kind"] == "synthetic"
    assert selected["ltt_outcome"]["sample_count"] == 101
    assert selected["runtime_eligible"] is False

    def forbidden(*args, **kwargs):
        pytest.fail("Evaluation must not fit or select on test")

    monkeypatch.setattr(calibration, "fit", forbidden)
    monkeypatch.setattr(utterance, "fit", forbidden)
    result = candidate.evaluate_candidate(
        report, fit, report, lock_path, report, tmp_path / "test.json"
    )
    assert result["split"] == "test" and result["sample_count"] == 4
    assert result["metrics"]["auc"] == 0.5
    assert result["metrics"]["eer"] == 0.5
    assert result["metrics"]["apcer_by_attack"] == {"tts": 0.0}
    assert result["metrics"]["max_apcer"] == 0
    assert result["metrics"]["bpcer"] == 1
    assert result["threshold"] == 0.25
    assert result["fixture_kind"] == "synthetic"
    assert result["ltt_report_sha256"] == hashlib.sha256(lock_path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "fault", ["provisional", "count", "excluded", "hash", "commit", "model", "dataset", "identity"]
)
def test_fit_envelope_mismatches_fail_closed(tmp_path, monkeypatch, fault):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, _, _ = fixture(tmp_path, monkeypatch, n=2)
    body = json.loads(fit.read_text())
    if fault == "provisional":
        body["artifact"]["provisional"] = True
    elif fault == "count":
        body["artifact"]["n_pos"] += 1
    elif fault == "excluded":
        body["excluded_calib_fit"] = {"error": 1}
    elif fault == "hash":
        body["measurement_report_sha256"] = "0" * 64
    elif fault == "commit":
        body["measurement_commit"] = "0" * 40
    elif fault == "model":
        body["artifact"]["model_version"] = "another-model"
    elif fault == "dataset":
        body["artifact"]["dataset"] = "another-dataset"
    else:
        body["artifact"]["method"] = "identity"
    write(fit, body)
    output = tmp_path / "forbidden.json"
    with pytest.raises(ValueError):
        candidate.score_report(report, fit, report, output, split="calib_ltt")
    assert not output.exists()


@pytest.mark.parametrize(
    "runtime",
    [
        {},
        {**RUNTIME, "system": "Darwin"},
        {**RUNTIME, "torch": "  "},
        {**RUNTIME, "cpu_threads": True},
        {**RUNTIME, "cpu_threads": "2"},
        {**RUNTIME, "cpu_threads": 0},
    ],
)
def test_runtime_must_be_explicit_strict_and_supported(tmp_path, monkeypatch, runtime):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, _, body = fixture(tmp_path, monkeypatch, n=2)
    body["runtime"] = runtime
    write(report, body)
    envelope = json.loads(fit.read_text())
    envelope["measurement_report_sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
    write(fit, envelope)
    with pytest.raises(ValueError):
        candidate.score_report(report, fit, report, tmp_path / "no.json", split="calib_ltt")


def sliced(body, split):
    body = copy.deepcopy(body)
    body["rows"] = [r for r in body["rows"] if r["sample"]["split"] == split]
    body["manifest"]["samples"] = [r["sample"] for r in body["rows"]]
    body["sample_count"] = len(body["rows"])
    return body


def separate(tmp_path, monkeypatch, *, failed=()):
    report, fit, protocol_path, body = fixture(tmp_path, monkeypatch, n=3, failed=failed)
    fit_measurement = write(tmp_path / "fit-measurement.json", sliced(body, "calib_fit"))
    fit.unlink()
    utterance.fit_report(fit_measurement, fit)
    write(report, sliced(body, "calib_ltt"))
    return report, fit, fit_measurement, protocol_path, body


@pytest.mark.parametrize(
    "fault",
    ["person", "secondary", "source", "bytes", "pcm", "overlap", "runtime", "parity", "dataset"],
)
def test_cross_report_leakage_and_binding_mismatches_rejected(tmp_path, monkeypatch, fault):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, fit_measurement, _, original = separate(tmp_path, monkeypatch)
    body = json.loads(report.read_text())
    fit_body = json.loads(fit_measurement.read_text())
    target = body["rows"][0]
    source = fit_body["rows"][0]
    if fault == "person":
        target["sample"]["subject_ids"] = source["sample"]["subject_ids"]
    elif fault == "secondary":
        target["sample"]["subject_ids"].extend(source["sample"]["subject_ids"])
    elif fault == "source":
        target["sample"]["source_group"] = source["sample"]["source_group"]
    elif fault == "bytes":
        target["sample"]["audio_sha256"] = source["sample"]["audio_sha256"]
    elif fault == "pcm":
        target["pcm_sha256"] = source["pcm_sha256"]
    elif fault == "overlap":
        body = original
    elif fault == "runtime":
        body["runtime"]["torch"] = "different-version"
    elif fault == "parity":
        body["parity_report_sha256"] = "f" * 64
    else:
        body["dataset"] = body["manifest"]["dataset"] = "different-dataset"
    body["manifest"]["samples"] = [r["sample"] for r in body["rows"]]
    samples = [utterance.Sample.model_validate(r["sample"]) for r in body["rows"]]
    groups = utterance._partition(samples, body["rows"])
    for row in body["rows"]:
        row["group_id"] = groups[row["sample"]["sample_id"]]
    write(report, body)
    output = tmp_path / "no.json"
    with pytest.raises(ValueError):
        candidate.score_report(report, fit, fit_measurement, output, split="calib_ltt")
    assert not output.exists()


def test_identical_full_report_deduplicates_by_digest(tmp_path, monkeypatch):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, _, _ = fixture(tmp_path, monkeypatch, n=3)
    same = tmp_path / "same.json"
    same.write_bytes(report.read_bytes())
    result = candidate.score_report(same, fit, report, tmp_path / "score.json", split="calib_ltt")
    assert result["sample_count"] == 4


@pytest.mark.parametrize("split", ["calib_ltt", "test"])
def test_failed_target_window_stops_instead_of_complete_case_filtering(
    tmp_path, monkeypatch, split
):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, protocol_path, _ = fixture(
        tmp_path, monkeypatch, failed=("s100" if split == "calib_ltt" else "s2000",)
    )
    output = tmp_path / "no.json"
    if split == "calib_ltt":
        with pytest.raises(ValueError):
            candidate.select_report(report, fit, report, protocol_path, output)
    else:
        lock = tmp_path / "selected.json"
        candidate.select_report(report, fit, report, protocol_path, lock)
        with pytest.raises(ValueError):
            candidate.evaluate_candidate(report, fit, report, lock, report, output)
    assert not output.exists()


@pytest.mark.parametrize("fault", ["selected", "outcome", "fit", "measurement", "protocol", "null"])
def test_evaluation_recomputes_locked_artifact_and_rejects_changed_references(
    tmp_path, monkeypatch, fault
):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, protocol_path, _ = fixture(tmp_path, monkeypatch)
    lock = tmp_path / "selected.json"
    body = candidate.select_report(report, fit, report, protocol_path, lock)
    if fault == "selected":
        body["selected"]["parameters"] = [0.75]
    elif fault == "outcome":
        body["ltt_outcome"]["candidates"][0]["statistically_valid"] = False
    elif fault == "fit":
        body["fit_report_sha256"] = "0" * 64
    elif fault == "measurement":
        body["measurement_report_sha256"] = "0" * 64
    elif fault == "protocol":
        declared = json.loads(protocol_path.read_text())
        declared["grid"] = [[0.75]]
        write(protocol_path, declared)
    else:
        body["selected"] = None
    write(lock, body)
    output = tmp_path / "no.json"
    with pytest.raises(ValueError):
        candidate.evaluate_candidate(report, fit, report, lock, report, output)
    assert not output.exists()


def test_no_selected_candidate_prevents_test_and_direct_test_scoring(tmp_path, monkeypatch):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, protocol_path, _ = fixture(tmp_path, monkeypatch, n=2)
    lock = tmp_path / "selected.json"
    body = candidate.select_report(report, fit, report, protocol_path, lock)
    assert body["selected"] is None
    with pytest.raises(ValueError):
        candidate.evaluate_candidate(report, fit, report, lock, report, tmp_path / "no.json")
    with pytest.raises(ValueError):
        candidate.score_report(report, fit, report, tmp_path / "no.json", split="test")


def test_input_mutation_during_scoring_leaves_no_output(tmp_path, monkeypatch):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, _, _ = fixture(tmp_path, monkeypatch, n=2)
    predict = calibration.Calibrator.predict

    def mutate(self, scores):
        report.write_bytes(report.read_bytes() + b" ")
        return predict(self, scores)

    monkeypatch.setattr(calibration.Calibrator, "predict", mutate)
    output = tmp_path / "no.json"
    with pytest.raises(ValueError, match="changed"):
        candidate.score_report(report, fit, report, output, split="calib_ltt")
    assert not output.exists()


@pytest.mark.parametrize("fault", ["slope_string", "count_float", "deployed_int"])
def test_fit_envelope_rejects_type_coercions(tmp_path, monkeypatch, fault):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, _, _ = fixture(tmp_path, monkeypatch, n=2)
    body = json.loads(fit.read_text())
    if fault == "slope_string":
        body["artifact"]["parameters"]["slope"] = "0.0"
    elif fault == "count_float":
        body["artifact"]["n_pos"] = 4.0
    else:
        body["deployed"] = 0
    write(fit, body)
    with pytest.raises(ValueError):
        candidate.score_report(report, fit, report, tmp_path / "no.json", split="calib_ltt")


def test_execution_commits_are_recorded_and_replay_preserves_selection_commit(
    tmp_path, monkeypatch
):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, protocol_path, _ = fixture(tmp_path, monkeypatch)
    lock = tmp_path / "lock.json"
    selected = candidate.select_report(report, fit, report, protocol_path, lock)
    assert selected["selection_commit"] == "d" * 40
    monkeypatch.setattr(utterance, "git_revision", lambda: "e" * 40)
    scored = candidate.score_report(
        report, fit, report, tmp_path / "scores.json", split="calib_ltt"
    )
    assert scored["scoring_commit"] == "e" * 40
    result = candidate.evaluate_candidate(report, fit, report, lock, report, tmp_path / "test.json")
    assert result["evaluation_commit"] == "e" * 40
    assert result["selection_commit"] == "d" * 40


@pytest.mark.parametrize("command", ["score", "select", "evaluate"])
def test_dirty_execution_source_stops_without_output(tmp_path, monkeypatch, command):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, protocol_path, _ = fixture(tmp_path, monkeypatch)
    lock = tmp_path / "lock.json"
    if command == "evaluate":
        candidate.select_report(report, fit, report, protocol_path, lock)
    monkeypatch.setattr(utterance, "git_revision", lambda: "e" * 40 + "-dirty")
    output = tmp_path / "no.json"
    with pytest.raises(ValueError):
        if command == "score":
            candidate.score_report(report, fit, report, output, split="calib_ltt")
        elif command == "select":
            candidate.select_report(report, fit, report, protocol_path, output)
        else:
            candidate.evaluate_candidate(report, fit, report, lock, report, output)
    assert not output.exists()


def test_failed_unused_row_is_still_a_cross_report_leakage_bridge(tmp_path, monkeypatch):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, fit_measurement, _, _ = separate(tmp_path, monkeypatch, failed=("s0",))
    body = json.loads(report.read_text())
    body["rows"][0]["sample"]["subject_ids"].append("person0")
    body["manifest"]["samples"] = [r["sample"] for r in body["rows"]]
    samples = [utterance.Sample.model_validate(r["sample"]) for r in body["rows"]]
    groups = utterance._partition(samples, body["rows"])
    for row in body["rows"]:
        row["group_id"] = groups[row["sample"]["sample_id"]]
    write(report, body)
    with pytest.raises(ValueError):
        candidate.score_report(
            report, fit, fit_measurement, tmp_path / "no.json", split="calib_ltt"
        )


def test_failed_unused_bridge_keeps_full_connected_group_for_ltt(tmp_path, monkeypatch):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, protocol_path, body = fixture(tmp_path, monkeypatch, failed=("s2000",))
    # Only the linked fitting measurement carries this failed LTT bridge. All
    # target observations are complete, so dropping the unused bridge would
    # incorrectly make its two attack identities look independent.
    target = sliced(body, "calib_ltt")
    fit_body = sliced(body, "calib_fit")
    bridge = copy.deepcopy(next(r for r in body["rows"] if r["sample"]["sample_id"] == "s2000"))
    bridge["sample"].update(
        sample_id="bridge",
        subject_ids=["person100", "person101"],
        source_group="bridge-source",
        audio_sha256="1" * 64,
        split="calib_ltt",
    )
    bridge["pcm_sha256"] = "2" * 64
    fit_body["rows"].append(bridge)
    fit_body["manifest"]["samples"] = [r["sample"] for r in fit_body["rows"]]
    fit_body["sample_count"] += 1
    samples = [utterance.Sample.model_validate(r["sample"]) for r in fit_body["rows"]]
    groups = utterance._partition(samples, fit_body["rows"])
    for row in fit_body["rows"]:
        row["group_id"] = groups[row["sample"]["sample_id"]]
    fit_measurement = write(tmp_path / "fit-measurement.json", fit_body)
    fit.unlink()
    utterance.fit_report(fit_measurement, fit)
    write(report, target)
    # Cannot silently discard failed rows to manufacture independent trials.
    with pytest.raises(ValueError, match="Repeated dependence group"):
        candidate.select_report(report, fit, fit_measurement, protocol_path, tmp_path / "no.json")


@pytest.mark.parametrize("target", ["input", "existing", "models", "config"])
def test_output_cannot_overwrite_inputs_or_enter_model_config_storage(
    tmp_path, monkeypatch, target
):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, _, _ = fixture(tmp_path, monkeypatch, n=2)
    if target == "input":
        output = report
    elif target == "existing":
        output = tmp_path / "existing.json"
        output.write_text("keep me")
    elif target == "models":
        monkeypatch.setenv("MODELS_DIR", str(tmp_path / "model-store"))
        output = tmp_path / "model-store" / "new.json"
    else:
        output = (
            Path(utterance.__file__).resolve().parents[4] / "ml/configs/forbidden-candidate.json"
        )
    original = report.read_bytes()
    with pytest.raises(ValueError):
        candidate.score_report(report, fit, report, output, split="calib_ltt")
    assert report.read_bytes() == original
    if target in ("models", "config"):
        assert not output.exists()
    if target == "existing":
        assert output.read_text() == "keep me"


def test_cli_smoke_produces_synthetic_locked_artifact(tmp_path, monkeypatch):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, protocol_path, _ = fixture(tmp_path, monkeypatch)
    output = tmp_path / "selected-cli.json"
    assert (
        candidate.main(
            [
                "select",
                "--report",
                str(report),
                "--fit-report",
                str(fit),
                "--fit-measurement",
                str(report),
                "--protocol",
                str(protocol_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text())["fixture_kind"] == "synthetic"


@pytest.mark.parametrize("kind", ["bonafide_only", "unexpected_attack", "attack_only"])
def test_test_coverage_gaps_are_explicit_without_selecting_new_thresholds(
    tmp_path, monkeypatch, kind
):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, protocol_path, body = fixture(tmp_path, monkeypatch)
    fit_measurement = write(tmp_path / "fit-measurement.json", sliced(body, "calib_fit"))
    ltt_measurement = write(tmp_path / "ltt-measurement.json", sliced(body, "calib_ltt"))
    fit.unlink()
    utterance.fit_report(fit_measurement, fit)
    test = sliced(body, "test")
    if kind == "bonafide_only":
        test["rows"] = [r for r in test["rows"] if not r["sample"]["label"]]
    elif kind == "attack_only":
        test["rows"] = [r for r in test["rows"] if r["sample"]["label"]]
    else:
        for row in test["rows"]:
            if row["sample"]["label"]:
                row["sample"]["attack_type"] = "vc"
    test["manifest"]["samples"] = [r["sample"] for r in test["rows"]]
    test["sample_count"] = len(test["rows"])
    write(report, test)
    lock = tmp_path / "locked.json"
    candidate.select_report(ltt_measurement, fit, fit_measurement, protocol_path, lock)
    result = candidate.evaluate_candidate(
        report, fit, fit_measurement, lock, ltt_measurement, tmp_path / "test.json"
    )
    assert result["evaluation_complete"] is False
    assert result["expected_attack_types"] == ["tts"]
    assert result["missing_expected_attack_types"] == ([] if kind == "attack_only" else ["tts"])
    assert result["unexpected_attack_types"] == (["vc"] if kind == "unexpected_attack" else [])
    assert result["class_coverage"]["bonafide"] is (kind != "attack_only")
    assert result["metrics"]["max_apcer_scope"] == "observed_attack_types_only"
    assert result["threshold"] == 0.25


def test_measured_linux_runtime_does_not_need_to_match_scoring_host(tmp_path, monkeypatch):
    from vericlue_ml.eval import nes2net_candidate as candidate

    report, fit, _, body = fixture(tmp_path, monkeypatch, n=2)
    body["runtime"]["system"] = "Linux"
    write(report, body)
    envelope = json.loads(fit.read_text())
    envelope["measurement_report_sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
    write(fit, envelope)
    result = candidate.score_report(
        report, fit, report, tmp_path / "scores.json", split="calib_ltt"
    )
    assert result["binding"]["runtime"]["system"] == "Linux"
