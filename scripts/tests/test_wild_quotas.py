"""DATA-03 regressions for scarce-class calibration groups and archive labels."""

from __future__ import annotations

import io
import json
import sys
import tarfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import make_image_splits as image  # noqa: E402
from make_splits import validate_splits  # noqa: E402


def test_wild_preserves_scarce_bonafide_groups_for_both_calibration_parts(monkeypatch) -> None:
    data_dir = Path("unused-data")
    rows = []
    for label, group_count, frames_per_group in (("0", 2, 100), ("1", 100, 2)):
        for group_index in range(group_count):
            origin = f"{label}/video-{group_index}"
            for frame in range(frames_per_group):
                rows.append(
                    image.row_for(
                        data_dir,
                        "wilddeepfake",
                        data_dir / f"raw/wilddeepfake/{origin}/{frame}.png",
                        label,
                        "bonafide" if label == "0" else "deepfake",
                        source_group=origin,
                    )
                )
    monkeypatch.setattr(image, "archive_rows", lambda *_: deepcopy(rows))

    first, report = image.wild_splits(data_dir, 42)
    repeated, _ = image.wild_splits(data_dir, 42)
    assert first == repeated
    assert report["video_groups"] == 102
    validate_splits(first, data_dir, check_files=False)
    part = first["wilddeepfake"]
    assert not part["train"]
    assert any(row["label"] == "1" for row in part["test"])
    memberships = {}
    for split, members in part.items():
        for row in members:
            assert memberships.setdefault(row["source_group"], split) == split
    assert sum(map(len, part.values())) == 400
    for split, minimum in (("calib_fit", 100), ("calib_ltt", 60)):
        counts = Counter(row["label"] for row in part[split])
        for label in ("0", "1"):
            assert counts[label] >= minimum, f"{split} label={label}: {counts[label]}/{minimum}"


def write_archive_index(data_dir: Path, source: str, source_split: str) -> None:
    folder = data_dir / "raw" / source
    folder.mkdir(parents=True)
    member = "video/frame.png"
    with tarfile.open(folder / "tiny.tar", "w") as archive:
        info = tarfile.TarInfo(member)
        info.size = 1
        archive.addfile(info, io.BytesIO(b"x"))
    record = {
        "archive": "tiny.tar",
        "member": member,
        "source_split": source_split,
        "video_origin_id": "source-video",
        "subject_id": "",
    }
    (folder / "video_groups.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")


def test_wild_rejects_unknown_source_split(tmp_path: Path) -> None:
    write_archive_index(tmp_path, "wilddeepfake", "unknown")
    with pytest.raises(ValueError):
        image.archive_rows(tmp_path, "wilddeepfake")


def test_vicocktail_train_split_remains_bonafide(tmp_path: Path) -> None:
    write_archive_index(tmp_path, "vicocktail", "train")
    rows = image.archive_rows(tmp_path, "vicocktail")
    assert len(rows) == 1
    assert rows[0]["label"] == "0"
    assert rows[0]["attack_type"] == "bonafide"
    assert rows[0]["source_group"] == "source-video"
