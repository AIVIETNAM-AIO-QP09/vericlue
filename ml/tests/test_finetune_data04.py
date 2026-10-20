"""FACE-04: hàm thuần chia tập theo nhóm, manifest, cổng lộ đề, ZIP từ xa (không có phần tạo giả)."""

from __future__ import annotations

import io
import zipfile

import numpy as np
import pytest

from vericlue_ml.finetune import data04 as d


# ── ZIP từ xa ─────────────────────────────────────────────────────────────────────────────
class _Response:
    def __init__(self, content: bytes, status: int = 206) -> None:
        self.content, self.status_code = content, status


class _RangeSession:
    def __init__(self, blob: bytes, status: int = 206) -> None:
        self.blob, self.status, self.calls = blob, status, 0

    def get(self, url, headers, timeout):
        self.calls += 1
        start, end = (int(v) for v in headers["Range"].split("=")[1].split("-"))
        return _Response(self.blob[start : end + 1], self.status)


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("part4/A/V1/V1_1.mp4", b"x" * 5000, compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            "part4/A/V1/V1_1.csv", b"word,a,b\n" * 50, compress_type=zipfile.ZIP_DEFLATED
        )
    return buffer.getvalue()


def _members(blob: bytes) -> list[d.ZipMember]:
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return [
            d.ZipMember(
                i.filename, i.header_offset, i.compress_size, i.file_size, i.compress_type, i.CRC
            )
            for i in archive.infolist()
        ]


def test_fetch_member_reads_stored_and_deflated_entries():
    blob = _zip_bytes()
    session = _RangeSession(blob)
    stored, deflated = _members(blob)
    assert d.fetch_member("u", stored, session) == b"x" * 5000
    assert d.fetch_member("u", deflated, session) == b"word,a,b\n" * 50


def test_fetch_member_rejects_server_without_range(monkeypatch):
    monkeypatch.setattr(d.time, "sleep", lambda _: None)
    blob = _zip_bytes()
    with pytest.raises(d.RemoteZipError):
        d.fetch_member("u", _members(blob)[0], _RangeSession(blob, status=200))


def test_decode_member_checks_crc():
    member = _members(_zip_bytes())[0]
    with pytest.raises(d.RemoteZipError):
        d.decode_member(member, b"y" * 5000)


# ── VLR ───────────────────────────────────────────────────────────────────────────────────
def test_parse_vlr_member():
    clip = d.parse_vlr_member("part4/HAVEA12/MOICH251/MOICH251_101.mp4", 10)
    assert clip is not None
    assert (clip.part, clip.playlist, clip.video, clip.index) == (
        "part4",
        "HAVEA12",
        "MOICH251",
        101,
    )
    assert clip.clip_id == "part4__HAVEA12__MOICH251__MOICH251_101"
    assert d.parse_vlr_member("part4/HAVEA12/MOICH251/MOICH251_101.csv") is None


def _clips():
    out = []
    for playlist in ("P1", "P2"):
        for v in range(4):
            for k in range(10):
                name = f"part4/{playlist}/{playlist}V{v}/{playlist}V{v}_{k}.mp4"
                out.append(d.parse_vlr_member(name))
    return out


def test_plan_candidates_deterministic_and_diverse():
    first = d.plan_candidates(_clips(), videos_per_part=4, clips_per_video=3, seed=7)
    again = d.plan_candidates(
        list(reversed(_clips())), videos_per_part=4, clips_per_video=3, seed=7
    )
    assert [c.clip_id for c in first] == [c.clip_id for c in again]
    assert len(first) == 12
    assert {c.playlist for c in first} == {"P1", "P2"}  # xen kẽ playlist


# ── gom người, chia tập ───────────────────────────────────────────────────────────────────
def _embeddings(n_persons: int, clips_each: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    centers = d.l2_normalize(rng.normal(size=(n_persons, 64)))
    embeddings, truth = [], []
    for p in range(n_persons):
        for _ in range(clips_each):
            frames = centers[p] + 0.05 * rng.normal(size=(3, 64))
            embeddings.append(d.l2_normalize(frames))
            truth.append(p)
    return embeddings, truth


def test_cluster_persons_recovers_identities_and_merges_transitively():
    embeddings, truth = _embeddings(5, 4)
    labels = d.cluster_persons(embeddings, threshold=0.5)
    assert len(set(labels)) == 5
    for a, b in zip(labels, truth, strict=True):
        assert labels[truth.index(b)] == a
    # Một clip "cầu" giống cả người 0 và người 1 → gộp cả hai (thà gộp nhầm).
    bridge = d.l2_normalize(np.stack([embeddings[0][0], embeddings[4][0]]))
    merged = d.cluster_persons([*embeddings, bridge], threshold=0.5)
    assert merged[0] == merged[4]


def test_group_components_joins_same_video():
    groups = d.group_components([0, 1, 2, 2], ["v1", "v1", "v2", "v3"])
    assert groups[0] == groups[1] and groups[2] == groups[3] and groups[0] != groups[2]


def test_assign_splits_ratio_and_determinism():
    weights = {f"g{i}": 1 for i in range(100)}
    a = d.assign_splits(weights, seed=3)
    assert a == d.assign_splits(dict(reversed(list(weights.items()))), seed=3)
    counts = {s: sum(1 for v in a.values() if v == s) for s in d.SPLITS}
    assert counts == {"train": 60, "calib": 20, "test": 20}


def test_full_person_split_has_no_cross_split_similarity():
    embeddings, _ = _embeddings(30, 3, seed=1)
    labels = d.cluster_persons(embeddings, threshold=0.5)
    videos = [f"v{i // 2}" for i in range(len(embeddings))]  # video nối các người kề nhau
    groups = d.group_components(labels, videos)
    persons_per_group: dict[str, set] = {}
    for g, p in zip(groups, labels, strict=True):
        persons_per_group.setdefault(str(g), set()).add(p)
    split_of_group = d.assign_splits({g: len(p) for g, p in persons_per_group.items()}, seed=0)
    split_of = [split_of_group[str(g)] for g in groups]
    assert d.cross_split_max_similarity(embeddings, split_of) < 0.5
    person_split: dict[int, str] = {}
    for p, s in zip(labels, split_of, strict=True):
        assert person_split.setdefault(p, s) == s


def test_select_persons_caps_and_interleaves_videos():
    person_of = [0] * 12 + [1] * 2 + [2]
    ids = [f"c{i:02d}" for i in range(15)]
    videos = ["a"] * 6 + ["b"] * 6 + ["c", "c", "d"]
    chosen = d.select_persons(
        person_of,
        ids,
        max_persons=2,
        max_clips_per_person=4,
        min_clips_per_person=2,
        seed=0,
        video_of=videos,
    )
    assert set(chosen) == {0, 1}
    assert len(chosen[0]) == 4
    assert {videos[ids.index(c)] for c in chosen[0]} == {"a", "b"}


# ── manifest ──────────────────────────────────────────────────────────────────────────────
def _row(**kw):
    row = dict.fromkeys(d.MANIFEST_FIELDS, "")
    row.update(variant="c23", split="train", label="real", person_id="p1", group_id="g1")
    row.update(kw)
    return row


def _good_rows():
    real = _row(sample_id="r1", source_clip="c1", dataset="forgerynet")
    fake = _row(sample_id="f1", source_clip="c1", label="fake", dataset="forgerynet", method="7")
    other = _row(sample_id="r2", source_clip="c2", person_id="p2", group_id="g2")
    return [real, fake, other]


def test_manifest_roundtrip_and_validation(tmp_path):
    rows = _good_rows()
    d.validate_manifest(rows)
    path = tmp_path / "manifest.csv"
    d.write_manifest(path, rows)
    back = d.read_manifest(path)
    assert {r["sample_id"] for r in back} == {"r1", "f1", "r2"}
    d.validate_manifest(back)


@pytest.mark.parametrize(
    "change",
    [
        {"method": ""},  # mẫu giả thiếu phương pháp
        {"split": "calib", "person_id": "p9"},  # nhóm g1 vắt hai tập
        {"split": "calib", "group_id": "g9"},  # người p1 vắt hai tập / khác tập với nguồn
        {"label": "maybe"},  # nhãn lạ
    ],
)
def test_manifest_validation_errors(change):
    rows = _good_rows()
    rows[1].update(change)
    with pytest.raises(ValueError):
        d.validate_manifest(rows)


def test_progress_resume(tmp_path):
    path = tmp_path / "state" / "progress.json"
    progress = d.Progress.load(path)
    progress.mark_failed("job1", "boom")
    progress.mark_done("job1", {"sec": 1.5})
    again = d.Progress.load(path)
    assert again.is_done("job1") and not again.failed
    assert again.done["job1"]["sec"] == 1.5


def test_encode_cmd_is_identical_for_both_classes():
    real = d.encode_cmd("ffmpeg", "a.mp4", "real.mp4", profile="c23")
    fake = d.encode_cmd("ffmpeg", "b.mp4", "fake.mp4", profile="c23", metadata={"comment": "x"})
    strip = lambda cmd: [x for x in cmd if x not in {"a.mp4", "b.mp4", "real.mp4", "fake.mp4"}]  # noqa: E731
    extra = [x for x in strip(fake) if x not in strip(real)]
    assert extra == ["-metadata", "comment=x"]
    assert "-an" in real and "-map_metadata" in real
    assert real[real.index("-crf") + 1] == "23"
    assert (
        d.encode_cmd("ffmpeg", "a", "b", profile="c40")[
            d.encode_cmd("ffmpeg", "a", "b", profile="c40").index("-crf") + 1
        ]
        == "40"
    )


# ── lộ đề ─────────────────────────────────────────────────────────────────────────────────
def _features(n: int, shift: float, seed: int):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        f = {name: float(rng.normal(100, 10)) for name in d.LEAK_FEATURES}
        f["bitrate_kbps"] += shift
        out.append(f)
    return out


def test_leak_auc_detects_shortcut_and_passes_clean_data():
    n = 60
    groups = [f"g{i}" for i in range(n)] * 2
    labels = [0] * n + [1] * n
    leaky = d.leak_auc(_features(n, 0, 1) + _features(n, 60, 2), labels, groups, seed=0)
    clean = d.leak_auc(_features(n, 0, 3) + _features(n, 0, 4), labels, groups, seed=0)
    assert leaky is not None and leaky > 0.9
    assert clean is not None and 0.3 < clean < 0.7


def test_leak_verdict():
    assert d.leak_verdict(0.5, 50, 50).ok
    stop = d.leak_verdict(0.8, 50, 50)
    assert not stop.ok and stop.enforced and "DỪNG" in stop.message_vi
    warn = d.leak_verdict(0.8, 5, 5)
    assert warn.ok and not warn.enforced and "CẢNH BÁO" in warn.message_vi
    assert not d.leak_verdict(None, 50, 50).ok


def test_video_features_on_synthetic_clip(tmp_path):
    cv2 = pytest.importorskip("cv2")
    path = tmp_path / "x.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 25, (64, 48))
    for i in range(25):
        writer.write(np.full((48, 64, 3), i * 5, dtype=np.uint8))
    writer.release()
    f = d.video_features(path)
    assert set(f) == set(d.LEAK_FEATURES)
    assert f["width"] == 64 and f["height"] == 48
    assert abs(f["duration_s"] - 1.0) < 0.1


def test_fake_with_source_in_other_split_is_rejected():
    rows = _good_rows()
    rows[1].update(split="calib", person_id="p3", group_id="g3")
    with pytest.raises(ValueError, match="nguồn"):
        d.validate_manifest(rows)
