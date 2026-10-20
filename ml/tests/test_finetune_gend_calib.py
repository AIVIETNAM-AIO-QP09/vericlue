"""FACE-04 (hiệu chỉnh GenD): chia RTFS, khung cắt, lệnh ffmpeg, lộ đề nguồn, báo cáo điểm."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vericlue_ml.common.calibration import CalibFit, fit
from vericlue_ml.finetune import gend_calib as gc


def _rtfs(n_videos: int = 30, n_photos: int = 20, seed: int = 0):
    rng = np.random.default_rng(seed)
    ids = [f"vid{i:08d}" for i in range(n_videos)]
    videos = [{"filename": f"{yid}_00001_00006.mp4"} for yid in ids]
    fakes = []
    for v in videos:
        for photo in rng.choice(n_photos, size=4, replace=False):
            for gen in ("inswapper", "uniface"):
                fakes.append(
                    {
                        "video": v["filename"],
                        "photo": f"1-{photo}.jpg",
                        "filename": f"{gen}_{v['filename'][:-4]}_1-{photo}_man.mp4",
                    }
                )
    return videos, fakes


def test_rtfs_youtube_id():
    assert gc.rtfs_youtube_id("inswapper_bdDhQL1aJcM_00008_00013_1-35_woman.mp4") == "bdDhQL1aJcM"
    assert gc.rtfs_youtube_id("bdDhQL1aJcM_00008_00013.mp4") == "bdDhQL1aJcM"
    assert gc.rtfs_youtube_id("abc.mp4") is None


def test_split_rtfs_cuts_single_component_without_donor_leak():
    videos, fakes = _rtfs()
    out = gc.split_rtfs(videos, fakes, seed=3)
    assert out.report["components_before_cut"] == 1  # như RTFS thật: một khối
    assert out.report["fakes_kept"] + out.report["fakes_dropped"] == len(fakes)
    assert out.report["fakes_kept"] > 0
    photo_split: dict[str, str] = {}
    for row in fakes:
        if row["filename"] in out.fake:
            split = out.fake[row["filename"]][0]
            assert out.real[row["video"]][0] == split
            assert photo_split.setdefault(row["photo"], split) == split
    assert set(out.real.values()) and {s for s, _ in out.real.values()} <= set(gc.CALIB_SPLITS)
    again = gc.split_rtfs(list(reversed(videos)), list(reversed(fakes)), seed=3)
    assert again.real == out.real and again.fake == out.fake


def test_split_rtfs_rejects_unknown_source():
    videos, fakes = _rtfs(3, 4)
    fakes[0] = {**fakes[0], "video": "zzzzzzzzzzz_00001_00002.mp4"}
    with pytest.raises(ValueError):
        gc.split_rtfs(videos, fakes, seed=0)


def test_check_rtfs_split_detects_donor_in_two_splits():
    real = {"a.mp4": ("calib_fit", "g1"), "b.mp4": ("calib_ltt", "g2")}
    fake = {"f1": ("calib_fit", "g1"), "f2": ("calib_ltt", "g2")}
    rows = [
        {"filename": "f1", "video": "a.mp4", "photo": "p"},
        {"filename": "f2", "video": "b.mp4", "photo": "p"},
    ]
    with pytest.raises(ValueError, match="donor"):
        gc.check_rtfs_split(real, fake, rows)


def test_person_groups_merge_same_person_and_same_video():
    rng = np.random.default_rng(0)
    a, b = rng.normal(size=(2, 16))
    emb = [np.stack([a, a]), np.stack([a + 0.01]), np.stack([b]), np.zeros((0, 16))]
    groups, report = gc.person_groups(
        emb, ["vlr", "vlr", "fas_vn", "vlr"], ["v1", "v2", "f1", "v3"], threshold=0.9
    )
    assert groups[0] == groups[1] != groups[2]
    assert groups[3] not in (groups[0], groups[2])
    assert report["groups"] == 3
    split = gc.split_groups(groups, seed=0)
    assert set(split) == set(groups)


def test_square_crop_box_inside_frame_and_even():
    x, y, side = gc.square_crop_box([[100, 100, 200, 220], [110, 105, 210, 230]], 1920, 1080)
    assert side % 2 == 0 and x % 2 == 0 and y % 2 == 0
    assert side == int(130 * gc.CROP_SCALE) // 2 * 2
    assert 0 <= x <= 1920 - side and 0 <= y <= 1080 - side
    x, y, side = gc.square_crop_box([[0, 0, 300, 300]], 320, 320)
    assert (x, y, side) == (0, 0, 320)
    with pytest.raises(ValueError):
        gc.square_crop_box([], 10, 10)


def test_crop_encode_cmd_same_for_video_and_still():
    video = gc.crop_encode_cmd("ffmpeg", "a.mp4", "o.mp4", (0, 0, 100))
    still = gc.crop_encode_cmd("ffmpeg", "a.jpg", "o.mp4", (0, 0, 100), still=True)
    for cmd in (video, still):
        assert cmd[cmd.index("-crf") + 1] == str(gc.ENCODE_CRF)
        assert "-an" in cmd and "-map_metadata" in cmd
        assert f"scale={gc.CROP_SIZE}:{gc.CROP_SIZE}" in cmd[cmd.index("-vf") + 1]
    assert "-t" in video and "-frames:v" in still


def test_fas_live_files_dedupes_and_drops_spoof_copies(tmp_path):
    live, spoof = tmp_path / "Image" / "train" / "live", tmp_path / "Image" / "train" / "not_live"
    live.mkdir(parents=True)
    spoof.mkdir(parents=True)
    (live / "a.jpg").write_bytes(b"A")
    (live / "b.jpg").write_bytes(b"A")  # trùng byte
    (live / "c.jpg").write_bytes(b"C")  # trùng ảnh giả
    (live / "d.jpg").write_bytes(b"D")
    (spoof / "x.jpg").write_bytes(b"C")
    keep, counts = gc.fas_live_files(tmp_path)
    assert [p.name for p in keep] == ["a.jpg", "d.jpg"]
    assert counts["duplicate"] == 1 and counts["live_equal_to_spoof"] == 1


def _feats(n, shift, seed):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        f = {k: float(rng.normal(100, 10)) for k in gc.LEAK_FEATURES}
        f["sharpness"] += shift
        out.append(f)
    return out


def test_source_leak_report_warns_but_does_not_raise():
    leaky = gc.source_leak_report(_feats(50, 0, 1) + _feats(50, 80, 2), [0] * 50 + [1] * 50)
    assert leaky["warning"] and "sharpness" in leaky["flagged"]
    assert "CẢNH BÁO" in leaky["message_vi"]
    clean = gc.source_leak_report(
        _feats(80, 0, 3) + _feats(80, 0, 4), [0] * 80 + [1] * 80, feature_names=("brightness",)
    )
    assert set(clean["auc"]) == {"brightness"}


def test_exceed_rates_and_summary():
    assert gc.exceed_rates([0.1, 0.2, 0.7]) == {"B": 2 / 3, "A": 1 / 3}
    assert gc.exceed_rates([]) == {"B": None, "A": None}
    rows = [{"source": "vlr", "label": 0, "score": s} for s in (0.1, 0.2, 0.3)]
    summary = gc.score_summary(rows)
    assert summary["vlr|that"]["n"] == 3 and summary["vlr|that"]["p50"] == pytest.approx(0.2)


def test_oof_probabilities_match_fit_folds():
    rng = np.random.default_rng(0)
    n = 120
    labels = [0] * n + [1] * n
    scores = np.clip(np.r_[rng.beta(2, 5, n), rng.beta(5, 2, n)], 0, 1).tolist()
    groups = [f"g{i % 30}" for i in range(2 * n)]
    cal = fit(
        CalibFit(scores=scores, labels=labels, subject_ids=groups, dataset="t"),
        module="face_deepfake",
        model_version="v",
        commit="c",
    )
    oof = gc.oof_probabilities(cal, scores, labels, groups)
    assert oof.shape == (2 * n,) and np.all((oof > 0) & (oof < 1))
    assert np.mean(oof[n:]) > np.mean(oof[:n])


def test_subset_sample_rows_eta():
    rows = [{"split": "calib_fit", "source": "vlr"}, {"split": "test", "source": "rtfs_fake"}]
    assert gc.subset(rows, split="calib_fit") == rows[:1]
    assert gc.subset(rows, source=("vlr", "rtfs_fake")) == rows
    assert gc.sample_rows(list(range(10)), 3, 0) == gc.sample_rows(list(range(10)), 3, 0)
    assert gc.sample_rows([1, 2], None, 0) == [1, 2]
    assert "còn khoảng" in gc.eta_text(5, 10, 60.0)


def test_expected_version_and_thresholds_match_config():
    import yaml

    from vericlue_ml.face.gend import AGGREGATION_TAG

    assert gc.EXPECTED_MODEL_VERSION.endswith(AGGREGATION_TAG)
    path = Path(__file__).resolve().parents[1] / "configs" / "thresholds.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert {"B": cfg["face"]["b"], "A": cfg["face"]["a"]} == gc.REPORT_THRESHOLDS


def test_fit_sources_exclude_vlr_but_keep_rtfs_real():
    assert "vlr" not in gc.FIT_SOURCES and "vlr" in gc.REFERENCE_SOURCES
    assert {"fas_vn", "rtfs_real", "rtfs_fake"} == set(gc.FIT_SOURCES)
    rows = [{"source": s} for s in ("vlr", "fas_vn", "rtfs_real", "rtfs_fake")]
    assert [r["source"] for r in gc.subset(rows, source=gc.FIT_SOURCES)] == [
        "fas_vn",
        "rtfs_real",
        "rtfs_fake",
    ]
