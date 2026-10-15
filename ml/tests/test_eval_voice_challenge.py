"""Full-manifest VOICE-04 evaluation without audio models or network."""

from __future__ import annotations

import json

import pytest

from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval import voice_challenge as evaluation
from vericlue_ml.eval.metrics import clopper_pearson


class FakeDetector:
    name = "voice_challenge"
    version = "fake-asr@test"

    def __init__(self, outcomes=None):
        self.calls = []
        self.outcomes = outcomes or {}

    def predict(self, inp):
        self.calls.append(inp)
        outcome = self.outcomes.get(inp.audio.name, ("ok", "pass"))
        if isinstance(outcome, Exception):
            raise outcome
        status, gate = outcome
        return ModuleResult(
            module=self.name,
            model_version=self.version,
            status=status,
            gate=gate,
            latency_ms=1,
            evidence=[{"type": "text", "name": "recognized_text", "value": "PRIVATE_TRANSCRIPT"}],
        )


@pytest.fixture
def manifest(tmp_path):
    folder = tmp_path / "data/raw/vimd"
    folder.mkdir(parents=True)
    rows = []
    for region in evaluation.REGIONS:
        for index in range(2):
            relative = f"{region}-{index}.wav"
            (folder / relative).write_bytes(b"synthetic-fixture")
            rows.append(
                {
                    "path": relative,
                    "region": region,
                    "subject_id": f"person-{region}",
                    "speakerID": f"person-{region}",
                    "text": "PRIVATE_EXPECTED xin chào bạn",
                }
            )
    path = folder / "selected_manifest.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    (folder / "SOURCE.md").write_text(
        f"- Revision: {evaluation.SOURCE_REVISION}\n", encoding="utf-8"
    )
    return path


def test_evaluates_every_sentence_and_counts_all_errors_in_operational_rate(manifest, monkeypatch):
    monkeypatch.setattr(
        evaluation, "_git_metadata", lambda: {"git_commit": "abc123", "working_tree_dirty": True}
    )
    detector = FakeDetector(
        {
            "North-1.wav": ("ok", "fail"),
            "Central-1.wav": ("error", "unclear"),
            "South-0.wav": ("degraded", "unclear"),
            "South-1.wav": RuntimeError("unknown-secret"),
        }
    )
    result = evaluation.evaluate_manifest(manifest, detector, expected_people_per_region=1)
    assert len(detector.calls) == 6
    assert {inp.audio.name for inp in detector.calls} == {
        f"{region}-{index}.wav" for region in evaluation.REGIONS for index in range(2)
    }
    assert all(inp.metadata["prompt"] == "PRIVATE_EXPECTED xin chào bạn" for inp in detector.calls)
    assert result["overall"]["n_sentences"] == 6
    assert result["overall"]["n_people"] == 3
    assert result["overall"]["n_mismatch"] == 1
    assert result["overall"]["n_processing_errors"] == 3
    assert result["overall"]["n_nonpass"] == 4
    assert result["overall"]["false_rejection_rate"] == pytest.approx(4 / 6)
    assert result["overall"]["cp95"] == clopper_pearson(4, 6)
    assert result["regions"]["North"]["cp95"] == clopper_pearson(1, 2)
    assert result["regions"]["South"]["false_rejection_rate"] == 1
    assert result["model_version"] == detector.version
    assert result["source_revision"] == evaluation.SOURCE_REVISION
    assert result["working_tree_dirty"] is True
    assert result["thresholds"] == {"max_syllable_wer": 0.3, "min_unaccented_similarity": 0.9}
    assert "unknown-secret" not in json.dumps(result)
    assert "độc lập" in result["limitations"]


def test_report_contains_aggregates_and_subjects_but_no_transcripts_or_paths(manifest):
    result = evaluation.evaluate_manifest(manifest, FakeDetector(), expected_people_per_region=1)
    report = evaluation.render_report(result)
    assert "PRIVATE_EXPECTED" not in report
    assert "PRIVATE_TRANSCRIPT" not in report
    assert str(manifest.parent) not in report
    assert "person-North" in report
    assert "CP95" in report
    assert "lỗi xử lý" in report


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_path",
        "missing_text",
        "missing_subject",
        "missing_region",
        "invalid_region",
        "mismatched_speaker",
        "missing_file",
        "duplicate_path",
        "cross_region_subject",
        "fake_label",
        "punctuation_text",
        "escape_path",
    ],
)
def test_validates_entire_manifest_before_first_inference(manifest, mutation):
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    last = rows[-1]
    if mutation.startswith("missing_") and mutation != "missing_file":
        key = {"missing_subject": "subject_id"}.get(mutation, mutation.removeprefix("missing_"))
        del last[key]
    elif mutation == "invalid_region":
        last["region"] = "unknown"
    elif mutation == "mismatched_speaker":
        last["speakerID"] = "other-person"
    elif mutation == "missing_file":
        last["path"] = "not-present.wav"
    elif mutation == "duplicate_path":
        last["path"] = rows[0]["path"]
    elif mutation == "cross_region_subject":
        last["subject_id"] = rows[0]["subject_id"]
        last["speakerID"] = rows[0]["speakerID"]
    elif mutation == "fake_label":
        last["label"] = "fake"
    elif mutation == "punctuation_text":
        last["text"] = "...?!"
    elif mutation == "escape_path":
        last["path"] = "../escape.wav"
    manifest.write_text(json.dumps(rows), encoding="utf-8")
    detector = FakeDetector()
    with pytest.raises(ValueError):
        evaluation.evaluate_manifest(manifest, detector, expected_people_per_region=1)
    assert detector.calls == []


def test_default_requires_twelve_people_four_per_region_before_inference(manifest):
    detector = FakeDetector()
    with pytest.raises(ValueError, match="4"):
        evaluation.evaluate_manifest(manifest, detector)
    assert detector.calls == []


def test_rejects_unpinned_source_revision_before_inference(manifest):
    manifest.with_name("SOURCE.md").write_text("- Revision: changed-source\n", encoding="utf-8")
    detector = FakeDetector()
    with pytest.raises(ValueError):
        evaluation.evaluate_manifest(manifest, detector, expected_people_per_region=1)
    assert detector.calls == []


def test_tts_correct_wrong_and_processing_error_are_all_reported(manifest):
    cases = []
    for name, should_match in [("correct.wav", True), ("wrong.wav", False), ("error.wav", False)]:
        (manifest.parent / name).write_bytes(b"synthetic-fixture")
        cases.append(
            {
                "path": name,
                "expected": "xin chào bạn",
                "spoken": "câu được nói",
                "should_match": should_match,
            }
        )
    tts = manifest.with_name("tts.json")
    tts.write_text(json.dumps(cases), encoding="utf-8")
    detector = FakeDetector({"wrong.wav": ("ok", "fail"), "error.wav": ("error", "unclear")})
    result = evaluation.evaluate_manifest(
        manifest, detector, expected_people_per_region=1, tts_manifest=tts
    )
    assert len(detector.calls) == 9
    assert result["tts"]["n_cases"] == 3
    assert result["tts"]["n_expected_match"] == 1
    assert result["tts"]["n_expected_mismatch"] == 2
    assert result["tts"]["n_correct_classification"] == 2
    assert result["tts"]["n_processing_errors"] == 1
    assert result["tts"]["details"][-1]["classification_correct"] is False


def test_cli_refuses_detailed_json_outside_data_eval_directory(manifest, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(manifest.parents[2]))
    monkeypatch.setattr(
        evaluation,
        "VoiceChallengeDetector",
        lambda: pytest.fail("unsafe output rejected before model setup"),
    )
    with pytest.raises(SystemExit) as error:
        evaluation.main(
            [
                "--manifest",
                str(manifest),
                "--output",
                str(tmp_path / "private.json"),
                "--report",
                str(tmp_path / "summary.md"),
            ]
        )
    assert error.value.code == 2
    assert not (tmp_path / "private.json").exists()


def test_cli_writes_private_json_and_aggregate_report(manifest, tmp_path, monkeypatch):
    original = evaluation.evaluate_manifest
    monkeypatch.setattr(
        evaluation,
        "evaluate_manifest",
        lambda path, detector, **kwargs: original(
            path, detector, expected_people_per_region=1, **kwargs
        ),
    )
    monkeypatch.setattr(evaluation, "VoiceChallengeDetector", FakeDetector)
    monkeypatch.setenv("DATA_DIR", str(manifest.parents[2]))
    output = manifest.parents[2] / "eval/VOICE04/details.json"
    report = tmp_path / "VOICE-04.md"
    assert (
        evaluation.main(
            ["--manifest", str(manifest), "--output", str(output), "--report", str(report)]
        )
        == 0
    )
    assert "PRIVATE_TRANSCRIPT" in output.read_text(encoding="utf-8")
    assert "PRIVATE_TRANSCRIPT" not in report.read_text(encoding="utf-8")


def test_ok_without_definitive_gate_is_processing_error_not_mismatch(manifest):
    detector = FakeDetector({"North-0.wav": ("ok", "unclear")})
    result = evaluation.evaluate_manifest(manifest, detector, expected_people_per_region=1)
    assert result["overall"]["n_sentences"] == 6
    assert result["overall"]["n_processing_errors"] == 1
    assert result["overall"]["n_mismatch"] == 0
    assert result["overall"]["n_nonpass"] == 1


def test_not_applicable_is_included_in_operational_nonpass(manifest):
    detector = FakeDetector({"North-0.wav": ("not_applicable", "unclear")})
    result = evaluation.evaluate_manifest(manifest, detector, expected_people_per_region=1)
    assert result["regions"]["North"]["n_processing_errors"] == 1
    assert result["regions"]["North"]["false_rejection_rate"] == 0.5


def test_invalid_tts_case_is_rejected_before_any_vimd_inference(manifest):
    tts = manifest.with_name("tts.json")
    tts.write_text(
        json.dumps(
            [
                {
                    "path": "missing.wav",
                    "expected": "xin chào bạn",
                    "spoken": "câu khác",
                    "should_match": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    detector = FakeDetector()
    with pytest.raises(ValueError):
        evaluation.evaluate_manifest(
            manifest, detector, expected_people_per_region=1, tts_manifest=tts
        )
    assert detector.calls == []
