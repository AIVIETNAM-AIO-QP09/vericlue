"""Evaluate every selected ViMD sentence with fixed VOICE-04 matching rules."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from vericlue_ml.common.detector import Detector, DetectorInput
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval.metrics import clopper_pearson
from vericlue_ml.voice.challenge import (
    MAX_SYLLABLE_WER,
    MIN_UNACCENTED_SIMILARITY,
    VoiceChallengeDetector,
    normalize_text,
)

REGIONS = ("North", "Central", "South")
SOURCE_REVISION = "3a5b30157034e7eadd5c75fae1a820c6f9383398"
ROOT = Path(__file__).resolve().parents[4]
LIMITATION = (
    "CP95 tính theo câu, giả định các câu độc lập; nhiều câu cùng người không độc lập. "
    "Chỉ có bốn người mỗi miền trong bản small; đây là thử nghiệm mô tả, "
    "chưa chứng minh công bằng theo miền. Lỗi xử lý được tính vào tỷ lệ không đạt. "
    "Không chọn mô hình hoặc ngưỡng từ các mẫu này. "
    "Thử nghiệm nhỏ; câu ViMD dài, chưa tương đương câu thử thách 8–12 âm tiết."
)


def _git_metadata() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return {"git_commit": commit, "working_tree_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"git_commit": "unavailable", "working_tree_dirty": None}


def _read_manifest(path: Path) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Manifest phải là danh sách không rỗng các bản ghi.")
    return rows


def _required_text(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Manifest thiếu trường văn bản {field}.")
    return value.strip()


def _audio_path(base: Path, value: str, *, allow_absolute: bool = False) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        if not allow_absolute:
            raise ValueError("Đường dẫn ViMD phải tương đối với thư mục manifest.")
        path = relative.resolve()
    else:
        path = (base / relative).resolve()
        if not path.is_relative_to(base.resolve()):
            raise ValueError("Đường dẫn audio thoát thư mục manifest.")
    if not path.is_file():
        raise ValueError("Không tìm thấy file audio được khai báo trong manifest.")
    return path


def _source_revision(manifest: Path) -> str:
    source = manifest.with_name("SOURCE.md").read_text(encoding="utf-8")
    match = re.search(r"^- Revision:\s*(\S+)", source, re.MULTILINE)
    if match is None or match[1] != SOURCE_REVISION:
        raise ValueError("SOURCE.md không khớp revision ViMD đã ghim cho VOICE-04.")
    return match[1]


def _predict(detector: Detector, path: Path, expected: str) -> dict[str, Any]:
    try:
        result = detector.predict(DetectorInput(audio=path, metadata={"prompt": expected}))
        if not isinstance(result, ModuleResult) or result.module != "voice_challenge":
            raise TypeError("Detector phải trả ModuleResult voice_challenge.")
        if result.status == "ok" and result.gate not in ("pass", "fail"):
            raise ValueError("Successful challenge requires a definitive gate.")
        return result.to_contract()
    except Exception as error:
        # Do not expose arbitrary backend messages, which may contain credentials.
        return {
            "module": "voice_challenge",
            "model_version": detector.version,
            "status": "error",
            "error_code": "E_INTERNAL",
            "gate": "unclear",
            "latency_ms": 0.0,
            "processing_error_type": type(error).__name__,
        }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = sum(row["result"]["status"] != "ok" for row in rows)
    mismatches = sum(
        row["result"]["status"] == "ok" and row["result"].get("gate") == "fail" for row in rows
    )
    nonpass = errors + mismatches
    speakers = sorted({row["subject_id"] for row in rows})
    return {
        "n_people": len(speakers),
        "speaker_ids": speakers,
        "n_sentences": len(rows),
        "n_mismatch": mismatches,
        "n_processing_errors": errors,
        "n_nonpass": nonpass,
        "false_rejection_rate": nonpass / len(rows),
        "cp95": clopper_pearson(nonpass, len(rows)),
        "processing_errors_included": True,
    }


def _tts_rows(manifest: Path) -> list[dict[str, Any]]:
    prepared = []
    for row in _read_manifest(manifest):
        expected = _required_text(row, "expected")
        spoken = _required_text(row, "spoken")
        should_match = row.get("should_match")
        if not isinstance(should_match, bool) or not normalize_text(expected):
            raise ValueError("TTS cần should_match dạng bool và câu expected hợp lệ.")
        path = _audio_path(manifest.parent, _required_text(row, "path"), allow_absolute=True)
        prepared.append(
            {
                "path": str(path),
                "expected": expected,
                "spoken": spoken,
                "should_match": should_match,
            }
        )
    return prepared


def evaluate_manifest(
    manifest: Path,
    detector: Detector,
    *,
    expected_people_per_region: int = 4,
    tts_manifest: Path | None = None,
) -> dict[str, Any]:
    """Validate and evaluate the entire manifest; never sample or fit thresholds."""
    if (
        isinstance(expected_people_per_region, bool)
        or not isinstance(expected_people_per_region, int)
        or expected_people_per_region < 1
    ):
        raise ValueError("Cần ít nhất một người mỗi miền.")
    manifest = manifest.resolve()
    revision = _source_revision(manifest)
    prepared, seen_paths, subject_regions = [], set(), {}
    for row in _read_manifest(manifest):
        region = _required_text(row, "region")
        if region not in REGIONS:
            raise ValueError("ViMD chỉ chấp nhận North, Central và South.")
        subject = _required_text(row, "subject_id")
        if row.get("speakerID") not in (None, subject):
            raise ValueError("speakerID không khớp subject_id.")
        if subject in subject_regions and subject_regions[subject] != region:
            raise ValueError("Một người xuất hiện ở nhiều miền.")
        subject_regions[subject] = region
        if "label" in row and row["label"] not in (0, "real", "human", "genuine", "bonafide"):
            raise ValueError("Chỉ đánh giá audio người thật ViMD nguyên bản.")
        expected = _required_text(row, "text")
        if not normalize_text(expected):
            raise ValueError("Transcript ViMD không có âm tiết.")
        path = _audio_path(manifest.parent, _required_text(row, "path"))
        if path in seen_paths:
            raise ValueError("Manifest chứa đường dẫn audio trùng.")
        seen_paths.add(path)
        prepared.append(
            {"path": str(path), "expected": expected, "region": region, "subject_id": subject}
        )
    for region in REGIONS:
        subjects = {row["subject_id"] for row in prepared if row["region"] == region}
        if len(subjects) != expected_people_per_region:
            raise ValueError(
                f"{region}: cần đúng {expected_people_per_region} người, có {len(subjects)}."
            )
    tts = _tts_rows(tts_manifest.resolve()) if tts_manifest is not None else []
    details = []
    for index, row in enumerate(prepared, start=1):
        details.append({**row, "result": _predict(detector, Path(row["path"]), row["expected"])})
        logging.getLogger(__name__).info("ViMD: %s/%s câu", index, len(prepared))
    regions = {
        region: _summarize([row for row in details if row["region"] == region])
        for region in REGIONS
    }
    summary = {
        "dataset": "ViMD selected_manifest (original human speech)",
        "manifest": str(manifest),
        "source_revision": revision,
        "model_version": detector.version,
        "date": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        **_git_metadata(),
        "thresholds": {
            "max_syllable_wer": MAX_SYLLABLE_WER,
            "min_unaccented_similarity": MIN_UNACCENTED_SIMILARITY,
        },
        "regions": regions,
        "overall": _summarize(details),
        "limitations": LIMITATION,
        "details": details,
    }
    if tts_manifest is not None:
        outcomes = [
            {**row, "result": _predict(detector, Path(row["path"]), row["expected"])} for row in tts
        ]
        for row in outcomes:
            row["classification_correct"] = (
                row["result"]["status"] == "ok"
                and (row["result"].get("gate") == "pass") == row["should_match"]
            )
        summary["tts"] = {
            "n_cases": len(outcomes),
            "n_expected_match": sum(row["should_match"] for row in outcomes),
            "n_expected_mismatch": sum(not row["should_match"] for row in outcomes),
            "n_correct_classification": sum(row["classification_correct"] for row in outcomes),
            "n_processing_errors": sum(row["result"]["status"] != "ok" for row in outcomes),
            "details": outcomes,
        }
    return summary


def render_report(result: dict[str, Any]) -> str:
    """Render aggregate counts only; transcripts and audio paths stay in local JSON."""
    lines = [
        "# VOICE-04 — Kiểm tra câu đọc",
        "",
        f"- Bộ dữ liệu: {result['dataset']}",
        f"- Commit: {result['git_commit']} (dirty={result['working_tree_dirty']})",
        f"- Mô hình: {result['model_version']}",
        f"- Revision dữ liệu: {result['source_revision']}",
        f"- Ngày: {result['date']}",
        f"- Ngưỡng cố định: WER ≤ {MAX_SYLLABLE_WER}; giống bỏ dấu ≥ {MIN_UNACCENTED_SIMILARITY}.",
        "- Tỷ lệ không đạt tính cả đọc sai và lỗi xử lý; không bỏ mẫu lỗi.",
        "",
        "| Miền | Người | Câu | Đọc sai | Lỗi xử lý | Không đạt | Tỷ lệ không đạt | CP95 theo câu |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, stats in [*result["regions"].items(), ("Tổng", result["overall"])]:
        low, high = stats["cp95"]
        lines.append(
            f"| {name} | {stats['n_people']} | {stats['n_sentences']} | {stats['n_mismatch']} | {stats['n_processing_errors']} | {stats['n_nonpass']} | {stats['false_rejection_rate']:.2%} | [{low:.2%}, {high:.2%}] |"
        )
    lines.extend(["", "## Giới hạn", "", result["limitations"], "", "## Người theo miền", ""])
    lines.extend(
        f"- {region}: {', '.join(stats['speaker_ids'])}"
        for region, stats in result["regions"].items()
    )
    if "tts" in result:
        tts = result["tts"]
        lines.extend(
            [
                "",
                "## TTS đọc đúng / đọc sai",
                "",
                f"{tts['n_cases']} ca: {tts['n_expected_match']} đọc đúng, {tts['n_expected_mismatch']} đọc sai; "
                f"{tts['n_correct_classification']} phân loại đúng, {tts['n_processing_errors']} lỗi xử lý.",
            ]
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run the full evaluation and keep detailed JSON under DATA_DIR/eval/VOICE04."""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--tts-manifest", type=Path)
    args = parser.parse_args(argv)
    data_dir = Path(os.environ.get("DATA_DIR", args.manifest.resolve().parents[2])).resolve()
    detail_root = data_dir / "eval" / "VOICE04"
    output, report = args.output.resolve(), args.report.resolve()
    if not output.is_relative_to(detail_root):
        parser.error("JSON chi tiết chỉ được lưu trong DATA_DIR/eval/VOICE04.")
    result = evaluate_manifest(
        args.manifest, VoiceChallengeDetector(), tts_manifest=args.tts_manifest
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report.write_text(render_report(result), encoding="utf-8")
    return (
        1
        if result["overall"]["n_processing_errors"]
        or result.get("tts", {}).get("n_processing_errors")
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
