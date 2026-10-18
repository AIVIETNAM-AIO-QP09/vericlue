"""DATA-03 image boundaries and archive provenance, without models/network."""

from __future__ import annotations

import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import make_image_splits as image  # noqa: E402
from make_splits import validate_splits  # noqa: E402


@pytest.mark.parametrize("member", ["../escape", "/absolute", "C:/drive", "a\\b"])
def test_archive_traversal_rejected(tmp_path, member):
    with pytest.raises(ValueError):
        image.safe_target(tmp_path, member)


def test_fas_quarantines_both_labels_by_bytes_not_filename(tmp_path):
    folder = tmp_path / "raw/fas_vn"
    folder.mkdir(parents=True)
    with zipfile.ZipFile(folder / "face-anti-spoofing.zip", "w") as archive:
        archive.writestr("Image/train_photo/live/first.jpg", b"duplicate")
        archive.writestr("Image/test_photo/not_live/second.jpg", b"duplicate")
        archive.writestr("Image/train_photo/not_live/face_image_live_ok.jpg", b"spoof")
    rows, quarantine = image.load_fas(tmp_path)
    assert len(quarantine) == 2
    assert quarantine[0]["sha256"] == quarantine[1]["sha256"]
    assert len(rows) == 1 and rows[0]["label"] == "1"
    assert (tmp_path / rows[0]["path"]).read_bytes() == b"spoof"


def test_cosine_union_transitive_and_cross_source(tmp_path):
    rows = [
        image.row_for(tmp_path, name, tmp_path / f"raw/{name}/{i}.jpg", "0", "bonafide")
        for i, name in enumerate(("zalo2022", "zalo2022", "fas_vn"))
    ]
    embeddings = [[np.array(v)] for v in ((1, 0), (0.8, 0.6), (0, 1))]
    groups = image.face_components(rows, embeddings, 0.55)
    assert len(groups) == 1
    assert len({r["group_id"] for r in rows}) == 1
    assert all(r["subject_id"] == "" for r in rows)


def wild_fixture(root, frames_per_archive=1):
    folder = root / "raw/wilddeepfake"
    folder.mkdir(parents=True)
    index = []
    # One source video appears in two archives. It must remain one component.
    for archive_index in range(2):
        name = f"shard-{archive_index}.tar"
        with tarfile.open(folder / name, "w") as archive:
            for label in ("real", "fake"):
                for video in range(20):
                    for frame in range(frames_per_archive):
                        member = f"{label}/{video}/{archive_index}-{frame}.png"
                        info = tarfile.TarInfo(member)
                        info.size = 100
                        archive.addfile(info, io.BytesIO(b"x" * 100))
                        index.append(
                            dict(
                                archive=name,
                                member=member,
                                source_split=f"{label}_train",
                                video_origin_id=f"{label}/{video}",
                                subject_id="",
                            )
                        )
    (folder / "video_groups.jsonl").write_text("\n".join(json.dumps(r) for r in index))


def test_wild_no_train_no_video_leak_reproducible_and_reports_shortage(tmp_path):
    wild_fixture(tmp_path)
    first, report = image.wild_splits(tmp_path, 42)
    second, _ = image.wild_splits(tmp_path, 42)
    assert first == second
    part = first["wilddeepfake"]
    assert not part["train"]
    assert report["video_groups"] == 40
    validate_splits(first, tmp_path)
    # Data is too small: LTT takes all 40 frames/class; fit/test cannot borrow it.
    assert len(part["calib_ltt"]) == 80
    assert not part["calib_fit"]
    summary = image.write_images(tmp_path, first, 42, report).read_text(encoding="utf-8")
    assert "thiếu 100" in summary


def test_wild_sufficient_quota_nonempty_three_parts_no_video_leak(tmp_path):
    wild_fixture(tmp_path, frames_per_archive=5)
    splits, _ = image.wild_splits(tmp_path, 42)
    repeated, _ = image.wild_splits(tmp_path, 42)
    assert splits == repeated
    validate_splits(splits, tmp_path)
    part = splits["wilddeepfake"]
    seen = {}
    for split in ("calib_fit", "calib_ltt", "test"):
        assert part[split]
        for row in part[split]:
            assert seen.setdefault(row["source_group"], split) == split
        for label in ("0", "1"):
            count = sum(row["label"] == label for row in part[split])
            assert count >= {"calib_fit": 100, "calib_ltt": 60, "test": 1}[split]
    assert not part["train"]


def test_zalo_forced_test_no_face_cross_fas_and_quotas(tmp_path, monkeypatch):
    folder = tmp_path / "raw/zalo2022"
    folder.mkdir(parents=True)
    records = []
    for i in range(500):
        (folder / f"{i}.mp4").touch()
        records.append(dict(path=f"{i}.mp4", source_video_id=str(i), liveness_score=str(i % 2)))
    (folder / "selected_manifest.json").write_text(json.dumps(records))
    fas_path = tmp_path / "raw/fas_vn/fas.jpg"
    fas_path.parent.mkdir(parents=True)
    fas_path.touch()
    fas = image.row_for(tmp_path, "fas_vn", fas_path, "0", "bonafide")
    monkeypatch.setattr(image, "load_fas", lambda _: ([fas], []))

    class Encoder:
        models = {"mock": "test-only"}

        def __init__(self, _):
            pass

        def encode(self, path):
            if path.stem == "0":
                return []
            index = 1 if path.stem == "fas" else int(path.stem)
            return [np.eye(500, dtype=np.float32)[index]]

        def close(self):
            pass

    monkeypatch.setattr(image, "FaceEncoder", Encoder)
    splits, report = image.zalo_splits(tmp_path, tmp_path, 42)
    validate_splits(splits, tmp_path)
    test_paths = {Path(r["path"]).stem for r in splits["zalo2022"]["test"]}
    assert {"0", "1"} <= test_paths
    assert splits["fas_vn"]["test"][0]["group_id"] == next(
        r["group_id"] for r in splits["zalo2022"]["test"] if Path(r["path"]).stem == "1"
    )
    for label in ("0", "1"):
        assert sum(r["label"] == label for r in splits["zalo2022"]["calib_fit"]) >= 100
    assert sum(r["label"] == "1" for r in splits["zalo2022"]["calib_ltt"]) >= 60
    assert report["no_face"] == {"zalo2022": 1}
    again, _ = image.zalo_splits(tmp_path, tmp_path, 42)
    assert again == splits


def test_rtfs_original_and_generators_share_video_and_donor(tmp_path):
    folder = tmp_path / "raw/rtfs10k"
    folder.mkdir(parents=True)
    (folder / "videos.csv").write_text("filename,id\na.mp4,youtube-a\nb.mp4,youtube-b\n")
    for name in ("a", "b"):
        path = folder / "original_videos" / f"{name}.mp4"
        path.parent.mkdir(exist_ok=True)
        path.touch()
    for generator, video in (("inswapper", "a"), ("uniface", "b")):
        (folder / f"{generator}.csv").write_text(
            f"filename,video,photo,success\nfake.mp4,{video}.mp4,donor.jpg,True\n"
        )
        path = folder / generator / "fake.mp4"
        path.parent.mkdir()
        path.touch()
    splits, _ = image.rtfs_splits(tmp_path)
    validate_splits(splits, tmp_path)
    assert all(not splits["rtfs10k"][split] for split in ("train", "calib_fit", "calib_ltt"))
    assert len(splits["rtfs10k"]["test"]) == 4
    assert len({r["group_id"] for r in splits["rtfs10k"]["test"]}) == 1


def test_source_pair_inherits_union_of_video_and_person(tmp_path, monkeypatch):
    pq = pytest.importorskip("pyarrow.parquet")
    import pyarrow as pa

    folder = tmp_path / "raw/vn_celeb_faces/data"
    folder.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {"image": {"bytes": b"photo", "path": None}, "label": f"person-{i // 2}"}
                for i in range(12)
            ]
        ),
        folder / "photos.parquet",
    )
    videos = []
    for i in range(8):
        path = tmp_path / f"raw/vicocktail/{i}.mp4"
        path.parent.mkdir(exist_ok=True)
        path.touch()
        videos.append(
            image.row_for(
                tmp_path, "vicocktail", path, "0", "bonafide", source_group=f"video-{i // 2}"
            )
        )
    monkeypatch.setattr(image, "archive_rows", lambda *args: videos)

    class Encoder:
        models = {"mock": "test-only"}

        def __init__(self, _):
            pass

        def encode(self, path):
            # All clips/photos link; the component cannot be cut to fill ratios.
            return [np.array([1, 0], dtype=np.float32)]

        def close(self):
            pass

    monkeypatch.setattr(image, "FaceEncoder", Encoder)
    splits, report = image.source_splits(tmp_path, tmp_path, 42)
    validate_splits(splits, tmp_path)
    assert report["input_groups"] == 10 and report["components"] == 1
    rows = [row for part in splits.values() for values in part.values() for row in values]
    assert len(rows) == 20
    assert len({row["group_id"] for row in rows}) == 1
