"""FOR-01 — kiểm tra chia đoạn và gộp khoảng nghi giả (thuần tính toán)."""

from __future__ import annotations

import random

import pytest

from vericlue_ml.forensic.segment import (
    INTERVAL_MARGIN_SECONDS,
    MIN_TAIL_SECONDS,
    SEGMENT_OVERLAP,
    SEGMENT_SECONDS,
    merge_flagged,
    plan_segments,
)

HOP = SEGMENT_SECONDS * (1 - SEGMENT_OVERLAP)


# --- plan_segments ----------------------------------------------------------


def test_video_60s_hop_1_5_va_doan_3s():
    segs = plan_segments(60)
    assert segs[0] == (0.0, 3.0)
    assert segs[1] == (1.5, 4.5)
    assert segs[-1] == (57.0, 60.0)
    assert len(segs) == 39
    assert all(b - a == pytest.approx(3.0) for a, b in segs)
    assert all(segs[i + 1][0] - segs[i][0] == pytest.approx(HOP) for i in range(len(segs) - 1))


@pytest.mark.parametrize("duration", [0.1, 1.0, 2.5, 3.0])
def test_file_ngan_hon_mot_doan_thi_mot_doan_bang_ca_file(duration):
    assert plan_segments(duration) == [(0.0, duration)]


@pytest.mark.parametrize("duration", [0, 0.0, None, -1, -0.5])
def test_thoi_luong_khong_hop_le_tra_rong(duration):
    assert plan_segments(duration) == []


def test_duoi_du_lon_them_doan_neo_cuoi_file():
    # 10 s: các đoạn đều kết thúc ở 9 s, còn dư 1 s >= MIN_TAIL_SECONDS
    segs = plan_segments(10)
    assert segs[-1] == (7.0, 10.0)
    assert segs[-2] == (6.0, 9.0)
    assert len(segs) == 6


def test_duoi_dung_bang_nguong_van_them_doan():
    segs = plan_segments(9 + MIN_TAIL_SECONDS)
    assert segs[-1][1] == pytest.approx(9.5)
    assert segs[-1][0] == pytest.approx(6.5)


def test_duoi_nho_hon_nguong_khong_them_doan():
    segs = plan_segments(9 + MIN_TAIL_SECONDS - 0.1)
    assert segs[-1] == (6.0, 9.0)
    assert len(segs) == 5


def test_moi_doan_nam_trong_khoang_0_den_duration():
    for duration in (0.7, 3.0, 3.2, 4.4, 10, 10.4, 17.9, 60, 61.3, 125.55):
        for a, b in plan_segments(duration):
            assert 0 <= a < b <= duration + 1e-9


def test_phu_kin_ca_file_tu_dau_den_cuoi():
    for duration in (4.0, 10, 10.4, 17.9, 61.3):
        segs = plan_segments(duration)
        assert segs[0][0] == 0.0
        assert segs[-1][1] == pytest.approx(duration)
        # không có khoảng hở giữa các đoạn liên tiếp
        assert all(segs[i + 1][0] <= segs[i][1] for i in range(len(segs) - 1))


def test_chong_lan_dung_50_phan_tram_giua_cac_doan_thuong():
    segs = plan_segments(60)  # không có đoạn neo cuối
    for (a0, b0), (a1, b1) in zip(segs, segs[1:], strict=False):
        overlap = b0 - a1
        assert overlap == pytest.approx(0.5 * (b0 - a0))
        assert b1 - a1 == pytest.approx(b0 - a0)


def test_doan_neo_cuoi_chong_lan_nhieu_hon_50_phan_tram():
    segs = plan_segments(10)
    (a0, b0), (a1, _b1) = segs[-2], segs[-1]
    assert (b0 - a1) / (b0 - a0) > 0.5


def test_tham_so_segment_va_overlap_tuy_chinh():
    segs = plan_segments(10, segment_s=2.0, overlap=0.0)
    assert segs == [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0), (6.0, 8.0), (8.0, 10.0)]


@pytest.mark.parametrize("overlap", [1.0, 1.5, -0.1])
def test_overlap_sai_nem_value_error(overlap):
    with pytest.raises(ValueError):
        plan_segments(60, overlap=overlap)


def test_overlap_sai_cung_bi_bat_voi_file_ngan():
    with pytest.raises(ValueError):
        plan_segments(2.0, overlap=1.5)


# --- merge_flagged ----------------------------------------------------------

SEGS_60 = plan_segments(60)


def _flags(n: int, *indices: int) -> list[bool]:
    return [i in indices for i in range(n)]


def test_khong_co_co_thi_khong_co_khoang():
    assert merge_flagged(SEGS_60, [False] * len(SEGS_60), 60) == []


def test_danh_sach_rong_thi_rong():
    assert merge_flagged([], [], 0) == []


def test_mot_doan_co_mo_rong_1s_hai_phia():
    # đoạn 10 = (15, 18)
    out = merge_flagged(SEGS_60, _flags(len(SEGS_60), 10), 60)
    assert out == [(14.0, 19.0, [10])]
    assert INTERVAL_MARGIN_SECONDS == 1.0


def test_khoang_bi_cat_vao_dau_file():
    out = merge_flagged(SEGS_60, _flags(len(SEGS_60), 0), 60)
    assert out == [(0.0, 4.0, [0])]


def test_khoang_bi_cat_vao_cuoi_file():
    last = len(SEGS_60) - 1
    out = merge_flagged(SEGS_60, _flags(len(SEGS_60), last), 60)
    assert out == [(56.0, 60.0, [last])]


def test_khoang_khong_vuot_duration_ngan_hon_doan_cuoi():
    # file ngắn: một đoạn duy nhất, cắt vào [0, duration]
    segs = plan_segments(2.0)
    assert merge_flagged(segs, [True], 2.0) == [(0.0, 2.0, [0])]


def test_hai_doan_lien_ke_thanh_mot_khoang():
    # đoạn 10 = (15, 18), đoạn 11 = (16.5, 19.5)
    out = merge_flagged(SEGS_60, _flags(len(SEGS_60), 10, 11), 60)
    assert out == [(14.0, 20.5, [10, 11])]


def test_ba_doan_lien_ke_thanh_mot_khoang():
    out = merge_flagged(SEGS_60, _flags(len(SEGS_60), 10, 11, 12), 60)
    assert out == [(14.0, 22.0, [10, 11, 12])]


def test_hai_nhom_xa_nhau_thanh_hai_khoang():
    # đoạn 5 = (7.5, 10.5) -> (6.5, 11.5); đoạn 20 = (30, 33) -> (29, 34)
    out = merge_flagged(SEGS_60, _flags(len(SEGS_60), 5, 20), 60)
    assert out == [(6.5, 11.5, [5]), (29.0, 34.0, [20])]


def test_khoang_cach_lon_hon_2s_van_tach_rieng():
    # đoạn 5 -> (6.5, 11.5); đoạn 9 = (13.5, 16.5) -> (12.5, 17.5): hở 1 s
    out = merge_flagged(SEGS_60, _flags(len(SEGS_60), 5, 9), 60)
    assert [(a, b) for a, b, _ in out] == [(6.5, 11.5), (12.5, 17.5)]


def test_hai_nhom_gan_nhau_sau_mo_rong_cham_thi_gop():
    segs = [(0.0, 3.0), (3.0, 5.0), (5.0, 8.0)]
    # (0, 3) -> (0, 4) và (5, 8) -> (4, 9): chạm đúng tại 4 s
    out = merge_flagged(segs, [True, False, True], 20)
    assert out == [(0.0, 9.0, [0, 2])]


def test_hai_nhom_cach_dung_2s_thanh_mot_khoang_khi_cham_nhau():
    segs = [(0.0, 3.0), (3.0, 4.0), (5.0, 8.0)]
    # (0, 4) và (4, 9): khoảng cách giữa hai nhóm đúng bằng 2 * margin
    assert merge_flagged(segs, [True, False, True], 20) == [(0.0, 9.0, [0, 2])]


def test_hai_nhom_cach_hon_2s_mot_chut_thi_tach():
    segs = [(0.0, 3.0), (3.0, 4.0), (6.0, 9.0)]
    out = merge_flagged(segs, [True, False, True], 20)
    assert out == [(0.0, 4.0, [0]), (5.0, 10.0, [2])]


def test_doan_khong_co_giua_hai_doan_co_cach_mot_doan_khong_la_lien_ke():
    # đoạn 10 và 12 cách một đoạn: hai NHÓM riêng, nhưng khoảng mở rộng chồng nhau nên gộp
    # (15,18)->(14,19) và (18,21)->(17,22) hở 0? 19 >= 17 nên chạm -> một khoảng
    out = merge_flagged(SEGS_60, _flags(len(SEGS_60), 10, 12), 60)
    assert out == [(14.0, 22.0, [10, 12])]


def test_doan_khong_co_khong_duoc_dua_vao_chi_so():
    out = merge_flagged(SEGS_60, _flags(len(SEGS_60), 10, 12), 60)
    assert 11 not in out[0][2]


def test_tra_dung_chi_so_doan_theo_thu_tu():
    flags = _flags(len(SEGS_60), 3, 4, 20, 21, 22, 38)
    out = merge_flagged(SEGS_60, flags, 60)
    assert [idx for _, _, idx in out] == [[3, 4], [20, 21, 22], [38]]
    assert sorted(i for _, _, idx in out for i in idx) == [3, 4, 20, 21, 22, 38]


def test_khong_bao_gio_chong_nhau_va_nam_trong_file():
    rng = random.Random(1234)
    for _ in range(200):
        duration = rng.choice([5.0, 10.0, 17.3, 60.0, 90.2])
        segs = plan_segments(duration)
        flags = [rng.random() < 0.3 for _ in segs]
        out = merge_flagged(segs, flags, duration)
        for a, b, idx in out:
            assert 0.0 <= a < b <= duration + 1e-9
            assert idx == sorted(idx)
        for (_, b0, _), (a1, _, _) in zip(out, out[1:], strict=False):
            assert b0 < a1  # hở thật sự, không chạm, không chồng
        # mọi đoạn có cờ đều được phủ
        for i, flagged in enumerate(flags):
            if flagged:
                assert any(i in idx for _, _, idx in out)
        covered = [i for _, _, idx in out for i in idx]
        assert len(covered) == len(set(covered)) == sum(flags)


def test_margin_tuy_chinh():
    out = merge_flagged(SEGS_60, _flags(len(SEGS_60), 10), 60, margin_s=0.0)
    assert out == [(15.0, 18.0, [10])]


def test_do_dai_khac_nhau_nem_value_error():
    with pytest.raises(ValueError):
        merge_flagged(SEGS_60, [True, False], 60)
    with pytest.raises(ValueError):
        merge_flagged([(0.0, 3.0)], [True, False], 3.0)
