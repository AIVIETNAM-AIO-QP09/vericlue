"""Kiểm audit độc lập bằng CSV nhỏ, không cần mô hình hoặc dữ liệu thật."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_image_splits import REQUIRED_FIELDS, SPLITS, audit  # noqa: E402


def write_splits(root: Path, dataset: str, rows: dict[str, list[dict]]) -> None:
    folder = root / "splits" / dataset
    folder.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        with (folder / f"{split}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=sorted(REQUIRED_FIELDS))
            writer.writeheader()
            for index, extra in enumerate(rows.get(split, [])):
                relative = f"raw/{dataset}/{split}_{index}.png"
                media = root / relative
                media.parent.mkdir(parents=True, exist_ok=True)
                media.touch()
                row = dict.fromkeys(REQUIRED_FIELDS, "")
                row.update(
                    path=relative,
                    label="0",
                    attack_type="bonafide",
                    source=dataset,
                    group_id=f"{dataset}:{split}:{index}",
                )
                row.update(extra)
                writer.writerow(row)


@pytest.mark.parametrize("field", ["subject_id", "source_group", "reference_group", "group_id"])
def test_reports_each_identity_boundary(tmp_path: Path, field: str) -> None:
    write_splits(
        tmp_path,
        "vn_celeb_faces",
        {"calib_fit": [{field: "same"}], "test": [{field: "same"}]},
    )
    result = audit(tmp_path, ("vn_celeb_faces",))
    assert any(f"Rò rỉ {field}/" in error for error in result["errors"])


def test_subjects_are_namespaced_but_components_are_global(tmp_path: Path) -> None:
    write_splits(tmp_path, "vn_celeb_faces", {"train": [{"subject_id": "001"}]})
    write_splits(tmp_path, "vicocktail", {"test": [{"subject_id": "001"}]})
    assert not audit(tmp_path, ("vn_celeb_faces", "vicocktail"))["errors"]
    write_splits(tmp_path, "vn_celeb_faces", {"train": [{"group_id": "cross-source"}]})
    write_splits(tmp_path, "vicocktail", {"test": [{"group_id": "cross-source"}]})
    assert any(
        "group_id/cross-source" in error
        for error in audit(tmp_path, ("vn_celeb_faces", "vicocktail"))["errors"]
    )


@pytest.mark.parametrize(
    "relative", ["../escape.png", "C:/external.png", "/absolute.png", "raw/vicocktail/missing.png"]
)
def test_rejects_unsafe_or_missing_paths(tmp_path: Path, relative: str) -> None:
    write_splits(tmp_path, "vicocktail", {"test": [{"path": relative}]})
    errors = audit(tmp_path, ("vicocktail",))["errors"]
    assert any(
        "path không tương đối" in error or "media không tồn tại" in error for error in errors
    )


@pytest.mark.parametrize(
    "relative",
    ["raw/other_source/existing.png", "raw/vicocktail_extra/existing.png", "existing.png"],
)
def test_rejects_existing_media_outside_source(tmp_path: Path, relative: str) -> None:
    media = tmp_path / relative
    media.parent.mkdir(parents=True, exist_ok=True)
    media.touch()
    write_splits(tmp_path, "vicocktail", {"test": [{"path": relative}]})
    errors = audit(tmp_path, ("vicocktail",))["errors"]
    assert any("path phải nằm trong raw/vicocktail/" in error for error in errors)


def test_rejects_backslashes_even_when_media_exists(tmp_path: Path) -> None:
    write_splits(tmp_path, "vicocktail", {"test": [{"path": r"raw\vicocktail\test_0.png"}]})
    assert (tmp_path / "raw/vicocktail/test_0.png").is_file()
    errors = audit(tmp_path, ("vicocktail",))["errors"]
    assert any("path không tương đối" in error for error in errors)


@pytest.mark.parametrize("directory", [False, True])
def test_rejects_symlink_to_another_source(tmp_path: Path, directory: bool) -> None:
    outside = tmp_path / "raw/other_source"
    outside.mkdir(parents=True)
    (outside / "media.png").touch()
    relative = "raw/vicocktail/escape/media.png" if directory else "raw/vicocktail/escape.png"
    write_splits(tmp_path, "vicocktail", {"test": [{"path": relative}]})
    link = tmp_path / "raw/vicocktail" / ("escape" if directory else "escape.png")
    target = outside if directory else outside / "media.png"
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        if os.name != "nt" or not directory:
            pytest.skip(f"Không có quyền tạo symlink trên máy test: {error}")
        # Windows directory junctions exercise the same resolve boundary without
        # requiring the privilege needed to create symbolic links.
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
    errors = audit(tmp_path, ("vicocktail",))["errors"]
    assert any("path phải nằm trong raw/vicocktail/" in error for error in errors)


def test_rejects_duplicate_path_in_same_split(tmp_path: Path) -> None:
    write_splits(
        tmp_path,
        "vicocktail",
        {"test": [{}, {"path": "raw/vicocktail/test_0.png"}]},
    )
    assert any("path trùng" in error for error in audit(tmp_path, ("vicocktail",))["errors"])


@pytest.mark.parametrize("dataset", ["fas_vn", "rtfs10k", "wilddeepfake"])
def test_forbidden_training_sources(tmp_path: Path, dataset: str) -> None:
    write_splits(tmp_path, dataset, {"train": [{"source_group": "video"}]})
    errors = audit(tmp_path, (dataset,))["errors"]
    assert any("chỉ được ở test" in error or "không có train" in error for error in errors)


def test_zalo_must_not_invent_subjects(tmp_path: Path) -> None:
    write_splits(tmp_path, "zalo2022", {"test": [{"subject_id": "invented"}]})
    assert any(
        "subject_id phải để trống" in error for error in audit(tmp_path, ("zalo2022",))["errors"]
    )


def test_small_valid_dataset_warns_quota_and_reports_group_counts(tmp_path: Path) -> None:
    write_splits(
        tmp_path,
        "wilddeepfake",
        {
            "calib_fit": [{"source_group": "v1"}, {"source_group": "v1", "group_id": "frame2"}],
            "calib_ltt": [{"source_group": "v2", "label": "1", "attack_type": "deepfake"}],
            "test": [{"source_group": "v3", "label": "1", "attack_type": "deepfake"}],
        },
    )
    report = audit(tmp_path, ("wilddeepfake",))
    assert not report["errors"]
    assert len(report["warnings"]) == 3
    fit = next(row for row in report["summary"] if row["split"] == "calib_fit")
    assert fit["samples"] == 2
    assert fit["video_groups"] == 1
    assert fit["counts"] == [{"label": "0", "attack_type": "bonafide", "samples": 2}]


def test_quota_is_error_when_train_has_enough_valid_donors(tmp_path: Path) -> None:
    write_splits(tmp_path, "zalo2022", {"train": [{} for _ in range(100)]})
    report = audit(tmp_path, ("zalo2022",))
    assert any("Quota chưa dồn đủ nhóm train" in error for error in report["errors"])
    fit = next(q for q in report["quotas"] if q["split"] == "calib_fit" and q["value"] == "0")
    assert fit["deficit"] == 100
    assert fit["train_donor_groups"] == 100


def test_missing_csv_and_schema_are_errors(tmp_path: Path) -> None:
    folder = tmp_path / "splits" / "zalo2022"
    folder.mkdir(parents=True)
    (folder / "train.csv").write_text("path,label\nimage.png,0\n", encoding="utf-8")
    errors = audit(tmp_path, ("zalo2022",))["errors"]
    assert len([error for error in errors if "Thiếu CSV" in error]) == 3
    assert any("thiếu cột" in error for error in errors)
