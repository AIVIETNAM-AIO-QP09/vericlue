"""FOR-01 — đọc metadata và cắt khung/âm thanh bằng file tổng hợp nhỏ (cv2, soundfile, wave)."""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

from vericlue_ml.forensic import media
from vericlue_ml.forensic.media import (
    MAX_DECODE_SECONDS,
    TARGET_SAMPLE_RATE,
    AudioUnavailable,
    FileMediaSource,
    MediaError,
    MediaInfo,
    _decode_with_ffmpeg,
    _decode_with_wave,
    _fourcc_to_str,
    _probe_ffprobe,
    _to_mono16k,
    _write_wav,
    probe_media,
)

VIDEO_FPS = 10
VIDEO_SECONDS = 7
VIDEO_W, VIDEO_H = 64, 48


def _make_video(path: Path) -> Path:
    cv2 = pytest.importorskip("cv2")
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), VIDEO_FPS, (VIDEO_W, VIDEO_H)
    )
    if not writer.isOpened():
        pytest.skip("cv2.VideoWriter không mở được mp4v trên máy này")
    for i in range(VIDEO_FPS * VIDEO_SECONDS):
        frame = np.zeros((VIDEO_H, VIDEO_W, 3), dtype=np.uint8)
        frame[:, :] = ((i * 7) % 256, (i * 13) % 256, (i * 29) % 256)
        writer.write(frame)
    writer.release()
    return path


def _make_wav(path: Path, seconds: float = 5.0, rate: int = 44100, freq: float = 440.0) -> Path:
    t = np.arange(int(seconds * rate)) / rate
    pcm = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())
    return path


def _read_wav(path: Path) -> tuple[np.ndarray, int, int, int]:
    with wave.open(str(path), "rb") as handle:
        raw = handle.readframes(handle.getnframes())
        return (
            np.frombuffer(raw, dtype="<i2"),
            handle.getframerate(),
            handle.getnchannels(),
            handle.getsampwidth(),
        )


# --- hàm thuần (không cần cv2/soundfile) ----------------------------------------


def test_write_wav_ghi_int16_mono_16khz_va_cat_bien(tmp_path):
    samples = np.array([0.0, 0.5, -0.5, 2.0, -3.0], dtype="float32")
    out = _write_wav(tmp_path / "sub" / "a.wav", samples)  # tự tạo thư mục cha
    data, rate, channels, width = _read_wav(out)
    assert (rate, channels, width) == (TARGET_SAMPLE_RATE, 1, 2)
    assert data.dtype == np.dtype("<i2")
    assert data.tolist() == [0, 16383, -16383, 32767, -32767]


def test_to_mono16k_giu_nguyen_khi_da_16khz():
    mono = np.linspace(-1, 1, 100, dtype="float32")
    assert np.array_equal(_to_mono16k(mono, TARGET_SAMPLE_RATE), mono)


def test_to_mono16k_stereo_lay_trung_binh_hai_kenh():
    stereo = np.stack([np.full(50, 0.2), np.full(50, 0.6)], axis=1).astype("float32")
    out = _to_mono16k(stereo, TARGET_SAMPLE_RATE)
    assert out.shape == (50,)
    assert out == pytest.approx(0.4)


def test_to_mono16k_lay_mau_lai_44k1_ve_16k():
    pytest.importorskip("scipy")
    one_second = np.zeros(44100, dtype="float32")
    assert _to_mono16k(one_second, 44100).size == TARGET_SAMPLE_RATE


def test_fourcc_to_str():
    assert _fourcc_to_str(0) is None
    assert _fourcc_to_str(-1) is None
    code = sum(ord(c) << (8 * i) for i, c in enumerate("mp4v"))
    assert _fourcc_to_str(float(code)) == "mp4v"


def test_media_info_to_dict_bo_notes():
    info = MediaInfo(kind="audio", size_bytes=10, duration_s=1.0, notes=["x"])
    data = info.to_dict()
    assert "notes" not in data
    assert data["kind"] == "audio" and data["duration_s"] == 1.0


def test_media_error_co_ma_va_audio_unavailable_co_ly_do():
    err = MediaError("hỏng")
    assert err.code == "unsupported_media" and str(err) == "hỏng"
    assert AudioUnavailable("không có tiếng").reason == "không có tiếng"


# --- video ----------------------------------------------------------------------


def test_probe_video_tong_hop(tmp_path):
    pytest.importorskip("cv2")
    path = _make_video(tmp_path / "clip.mp4")
    info = probe_media(path)
    assert info.kind == "video"
    assert info.width == VIDEO_W and info.height == VIDEO_H
    assert info.fps == pytest.approx(VIDEO_FPS, abs=0.5)
    assert info.duration_s == pytest.approx(VIDEO_SECONDS, abs=0.5)
    assert info.size_bytes == path.stat().st_size
    assert info.has_audio in (None, False)  # None nếu thiếu PyAV; False nếu có PyAV
    assert info.bitrate_kbps and info.bitrate_kbps > 0


def test_frames_tra_toi_da_4_png_doc_duoc(tmp_path):
    cv2 = pytest.importorskip("cv2")
    source = FileMediaSource(_make_video(tmp_path / "clip.mp4"))
    outdir = tmp_path / "frames"
    paths = source.frames(0, 3, 4, outdir)
    assert 1 <= len(paths) <= 4
    assert all(p.suffix == ".png" and p.parent == outdir for p in paths)
    assert paths == sorted(paths)
    for p in paths:
        img = cv2.imread(str(p))
        assert img is not None and img.shape == (VIDEO_H, VIDEO_W, 3)


def test_frames_mot_khung_lay_khung_giua(tmp_path):
    pytest.importorskip("cv2")
    source = FileMediaSource(_make_video(tmp_path / "clip.mp4"))
    paths = source.frames(2, 4, 1, tmp_path / "f")
    assert len(paths) == 1
    # khung 20..39 -> giữa = 29 (10 fps)
    assert paths[0].name == "f0000029.png"


def test_frames_doan_cuoi_van_doc_duoc(tmp_path):
    pytest.importorskip("cv2")
    source = FileMediaSource(_make_video(tmp_path / "clip.mp4"))
    paths = source.frames(4.0, 7.0, 4, tmp_path / "tail")
    assert len(paths) >= 3


def test_frames_tham_so_vo_ly_tra_rong(tmp_path):
    pytest.importorskip("cv2")
    source = FileMediaSource(_make_video(tmp_path / "clip.mp4"))
    assert source.frames(0, 3, 0, tmp_path / "a") == []
    assert source.frames(3, 3, 4, tmp_path / "b") == []
    assert source.frames(5, 1, 4, tmp_path / "c") == []


def test_video_khong_tieng_audio_wav_nem_audio_unavailable(tmp_path):
    pytest.importorskip("cv2")
    source = FileMediaSource(_make_video(tmp_path / "clip.mp4"))
    with pytest.raises(AudioUnavailable) as exc:
        source.audio_wav(0, 3, tmp_path / "a.wav")
    assert exc.value.reason
    with pytest.raises(AudioUnavailable):
        source.full_audio_wav(tmp_path / "full.wav")
    assert not (tmp_path / "a.wav").exists()
    # lần gọi sau dùng lại lỗi đã nhớ, vẫn cùng một loại ngoại lệ
    with pytest.raises(AudioUnavailable):
        source.audio_wav(0, 3, tmp_path / "b.wav")


def test_video_khong_bi_ghi_de_khi_doc(tmp_path):
    pytest.importorskip("cv2")
    path = _make_video(tmp_path / "clip.mp4")
    before = path.read_bytes()
    source = FileMediaSource(path)
    source.frames(0, 3, 4, tmp_path / "f")
    assert path.read_bytes() == before


# --- âm thanh -----------------------------------------------------------------


def test_probe_wav_la_audio_5s(tmp_path):
    info = probe_media(_make_wav(tmp_path / "tone.wav"))
    assert info.kind == "audio"
    assert info.duration_s == pytest.approx(5.0, abs=0.05)
    assert info.audio_sample_rate == 44100
    assert info.container == "wav"
    assert info.has_audio is True
    assert info.width is None and info.fps is None


def test_audio_wav_cat_doan_1_den_4s_thanh_wav_16k_mono(tmp_path):
    pytest.importorskip("scipy")
    source = FileMediaSource(_make_wav(tmp_path / "tone.wav"))
    out = source.audio_wav(1, 4, tmp_path / "out" / "seg.wav")
    data, rate, channels, width = _read_wav(out)
    assert (rate, channels, width) == (16000, 1, 2)
    assert data.size == pytest.approx(3 * 16000, abs=2)
    assert 10000 < np.abs(data).max() < 20000  # biên độ 0,5 -> ~16383
    # tần số trội vẫn ~440 Hz sau khi lấy mẫu lại
    spectrum = np.abs(np.fft.rfft(data.astype("float32")))
    freq = spectrum.argmax() * 16000 / data.size
    assert freq == pytest.approx(440, abs=5)


def test_full_audio_wav_khoang_5s(tmp_path):
    pytest.importorskip("scipy")
    source = FileMediaSource(_make_wav(tmp_path / "tone.wav"))
    data, rate, channels, _ = _read_wav(source.full_audio_wav(tmp_path / "full.wav"))
    assert (rate, channels) == (16000, 1)
    assert data.size / rate == pytest.approx(5.0, abs=0.01)


def test_audio_wav_cua_so_vuot_cuoi_file_bi_cat(tmp_path):
    pytest.importorskip("scipy")
    source = FileMediaSource(_make_wav(tmp_path / "tone.wav"))
    data, _, _, _ = _read_wav(source.audio_wav(4, 9, tmp_path / "tail.wav"))
    assert data.size == pytest.approx(16000, abs=2)


def test_wav_16k_khong_lay_mau_lai_dung_so_mau(tmp_path):
    source = FileMediaSource(_make_wav(tmp_path / "tone16.wav", seconds=2, rate=16000))
    data, rate, _, _ = _read_wav(source.audio_wav(0.5, 1.5, tmp_path / "s.wav"))
    assert rate == 16000 and data.size == 16000


def test_audio_frames_tra_rong(tmp_path):
    source = FileMediaSource(_make_wav(tmp_path / "tone.wav", seconds=2))
    assert source.frames(0, 2, 4, tmp_path / "f") == []


# --- file rác -------------------------------------------------------------------


def test_file_rac_nem_media_error(tmp_path):
    pytest.importorskip("cv2")
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"day khong phai media " * 100)
    with pytest.raises(MediaError) as exc:
        probe_media(junk)
    assert exc.value.code == "unsupported_media"
    with pytest.raises(MediaError):
        FileMediaSource(junk)


def test_file_rong_nem_media_error(tmp_path):
    pytest.importorskip("cv2")
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(MediaError):
        probe_media(empty)


# --- _decode_with_wave (thư viện chuẩn, không cần soundfile) -------------------------


def _wav_bytes(path: Path, frames: bytes, *, width: int, channels: int = 1, rate: int = 16000):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(width)
        handle.setframerate(rate)
        handle.writeframes(frames)
    return path


def _le(value: int, width: int) -> bytes:
    return (value & ((1 << (8 * width)) - 1)).to_bytes(width, "little")


@pytest.mark.parametrize(
    ("width", "positive", "negative"),
    [
        (1, bytes([192]), bytes([64])),  # (192-128)/128 = 0,5
        (2, _le(16384, 2), _le(-16384, 2)),
        (3, _le(1 << 22, 3), _le(-(1 << 22), 3)),
        (4, _le(1 << 30, 4), _le(-(1 << 30), 4)),
    ],
)
def test_decode_with_wave_pcm_8_16_24_32_bit(tmp_path, width, positive, negative):
    path = _wav_bytes(tmp_path / f"w{width}.wav", positive * 800 + negative * 800, width=width)
    data = _decode_with_wave(path)
    assert data is not None and data.dtype == np.float32
    assert data.size == 1600
    assert data[:800] == pytest.approx(0.5, abs=1e-3)
    assert data[800:] == pytest.approx(-0.5, abs=1e-3)


def test_decode_with_wave_stereo_ve_mono(tmp_path):
    left = _le(int(0.2 * 32768), 2)
    right = _le(int(0.6 * 32768), 2)
    path = _wav_bytes(tmp_path / "st.wav", (left + right) * 500, width=2, channels=2)
    data = _decode_with_wave(path)
    assert data is not None and data.shape == (500,)
    assert data == pytest.approx(0.4, abs=1e-3)


def test_decode_with_wave_44k1_ve_16k(tmp_path):
    pytest.importorskip("scipy")
    data = _decode_with_wave(_make_wav(tmp_path / "t.wav", seconds=1.0, rate=44100))
    assert data is not None and data.size == TARGET_SAMPLE_RATE


@pytest.mark.parametrize(
    "content",
    [b"", b"day khong phai wav " * 50, b"RIFF\x00\x00\x00\x00WAVE", b"\x00\x01" * 100],
)
def test_decode_with_wave_file_rac_tra_none(tmp_path, content):
    junk = tmp_path / "junk.wav"
    junk.write_bytes(content)
    assert _decode_with_wave(junk) is None


def test_decode_with_wave_file_khong_ton_tai_tra_none(tmp_path):
    assert _decode_with_wave(tmp_path / "nope.wav") is None


def test_decode_with_wave_khong_phai_wav_pcm_tra_none(tmp_path):
    mp4 = _make_video(tmp_path / "c.mp4")
    assert _decode_with_wave(mp4) is None


# --- không có soundfile -------------------------------------------------------------


def test_probe_wav_khong_co_soundfile_dung_nhanh_wave(tmp_path, monkeypatch):
    path = _make_wav(tmp_path / "tone.wav", seconds=5.0, rate=44100)
    monkeypatch.setitem(sys.modules, "soundfile", None)  # import soundfile -> ImportError
    monkeypatch.setitem(sys.modules, "cv2", None)
    info = probe_media(path)
    assert info.kind == "audio"
    assert info.duration_s == pytest.approx(5.0, abs=0.01)
    assert info.audio_sample_rate == 44100
    assert info.container == "wav"
    assert info.has_audio is True
    assert any("soundfile" in n for n in info.notes)


def test_audio_wav_chay_duoc_khong_co_soundfile(tmp_path, monkeypatch):
    path = _make_wav(tmp_path / "tone16.wav", seconds=3, rate=16000)
    monkeypatch.setitem(sys.modules, "soundfile", None)
    monkeypatch.setitem(sys.modules, "cv2", None)
    source = FileMediaSource(path)
    data, rate, channels, _ = _read_wav(source.audio_wav(1, 2, tmp_path / "s.wav"))
    assert (rate, channels) == (16000, 1)
    assert data.size == 16000
    full, _, _, _ = _read_wav(source.full_audio_wav(tmp_path / "full.wav"))
    assert full.size == 3 * 16000


def test_audio_wav_44k1_khong_co_soundfile(tmp_path, monkeypatch):
    pytest.importorskip("scipy")
    path = _make_wav(tmp_path / "tone.wav", seconds=5.0, rate=44100)
    monkeypatch.setitem(sys.modules, "soundfile", None)
    monkeypatch.setitem(sys.modules, "cv2", None)
    source = FileMediaSource(path)
    data, rate, _, _ = _read_wav(source.audio_wav(1, 4, tmp_path / "s.wav"))
    assert rate == 16000 and data.size == pytest.approx(3 * 16000, abs=2)


# --- ffmpeg / ffprobe qua subprocess (giả) ---------------------------------------------


@pytest.fixture
def fake_tools(tmp_path, monkeypatch):
    """FFMPEG_BINARY/FFPROBE_BINARY trỏ file tạm; subprocess.run bị thay bằng bản ghi lệnh."""
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg.write_bytes(b"")
    ffprobe.write_bytes(b"")
    monkeypatch.setenv("FFMPEG_BINARY", str(ffmpeg))
    monkeypatch.setenv("FFPROBE_BINARY", str(ffprobe))
    state = {"calls": [], "behaviour": None, "ffmpeg": ffmpeg, "ffprobe": ffprobe}

    def fake_run(command, **kwargs):
        state["calls"].append((command, kwargs))
        return state["behaviour"](command, kwargs)

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    return state


def _pcm_bytes(seconds: float = 1.0) -> bytes:
    return (np.full(int(16000 * seconds), 1000, dtype="<i2")).tobytes()


def _arg_after(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


def test_ffmpeg_goi_voi_protocol_whitelist_file_pipe_va_khong_qua_shell(fake_tools, tmp_path):
    fake_tools["behaviour"] = lambda c, k: subprocess.CompletedProcess(c, 0, _pcm_bytes(), b"")
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    samples = _decode_with_ffmpeg(clip)
    assert samples is not None and samples.size == 16000
    ((command, kwargs),) = fake_tools["calls"]
    assert isinstance(command, list)
    assert command[0] == str(fake_tools["ffmpeg"])
    assert _arg_after(command, "-protocol_whitelist") == "file,pipe"
    assert command.index("-protocol_whitelist") < command.index("-i")  # tùy chọn của đầu vào
    assert _arg_after(command, "-i") == str(clip)
    assert _arg_after(command, "-ar") == "16000" and _arg_after(command, "-ac") == "1"
    assert not kwargs.get("shell")
    assert kwargs.get("timeout")
    assert MAX_DECODE_SECONDS == 600
    assert _arg_after(command, "-t") == str(MAX_DECODE_SECONDS)
    assert command.index("-t") < command.index("-f")  # giới hạn trước định dạng đầu ra
    assert _arg_after(command, "-f") == "s16le"


def test_ffprobe_goi_voi_protocol_whitelist_file_pipe(fake_tools, tmp_path):
    payload = {
        "format": {"format_name": "mov,mp4,m4a", "duration": "7.5"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264"},
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000"},
        ],
    }
    fake_tools["behaviour"] = lambda c, k: subprocess.CompletedProcess(
        c, 0, json.dumps(payload).encode(), b""
    )
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    info = _probe_ffprobe(clip)
    ((command, kwargs),) = fake_tools["calls"]
    assert isinstance(command, list) and command[0] == str(fake_tools["ffprobe"])
    assert _arg_after(command, "-protocol_whitelist") == "file,pipe"
    assert command[-1] == str(clip)
    assert not kwargs.get("shell")
    assert info == {
        "container": "mov",
        "duration_s": 7.5,
        "has_audio": True,
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
    }


def _source_for_junk_video(tmp_path, monkeypatch) -> FileMediaSource:
    """FileMediaSource trên file không phải WAV (như mp4); tắt PyAV để chỉ còn ffmpeg."""
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"khong phai wav " * 20)
    monkeypatch.setattr(
        media, "probe_media", lambda p: MediaInfo(kind="video", size_bytes=1, duration_s=5.0)
    )
    monkeypatch.setattr(media, "_decode_with_av", lambda p: None)
    return FileMediaSource(clip)


def test_audio_wav_dung_ffmpeg_khi_cac_cach_khac_khong_giai_ma_duoc(
    fake_tools, tmp_path, monkeypatch
):
    fake_tools["behaviour"] = lambda c, k: subprocess.CompletedProcess(c, 0, _pcm_bytes(2), b"")
    source = _source_for_junk_video(tmp_path, monkeypatch)
    data, rate, channels, _ = _read_wav(source.audio_wav(0, 1, tmp_path / "s.wav"))
    assert (rate, channels, data.size) == (16000, 1, 16000)
    assert data[0] == pytest.approx(1000, abs=1)
    source.full_audio_wav(tmp_path / "full.wav")
    assert len(fake_tools["calls"]) == 1  # giải mã một lần rồi nhớ


def test_ffmpeg_het_gio_thi_audio_unavailable_voi_ly_do_qua_thoi_gian(
    fake_tools, tmp_path, monkeypatch
):
    def timeout(command, kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 1))

    fake_tools["behaviour"] = timeout
    source = _source_for_junk_video(tmp_path, monkeypatch)
    for call in (
        lambda: source.audio_wav(0, 3, tmp_path / "a.wav"),
        lambda: source.full_audio_wav(tmp_path / "f.wav"),
    ):
        with pytest.raises(AudioUnavailable) as exc:
            call()
        assert "quá thời gian" in exc.value.reason
        assert "chưa có" not in exc.value.reason  # không phải câu "thiếu ffmpeg"


def test_ffmpeg_loi_khong_ra_mau_nao_thi_khong_co_luong_tieng(fake_tools, tmp_path, monkeypatch):
    fake_tools["behaviour"] = lambda c, k: subprocess.CompletedProcess(c, 1, b"", b"loi")
    source = _source_for_junk_video(tmp_path, monkeypatch)
    with pytest.raises(AudioUnavailable) as exc:
        source.audio_wav(0, 3, tmp_path / "a.wav")
    assert "không có luồng âm thanh" in exc.value.reason


def test_khong_co_ffmpeg_thi_hanh_vi_cu_va_khong_goi_subprocess(tmp_path, monkeypatch):
    monkeypatch.delenv("FFMPEG_BINARY", raising=False)
    monkeypatch.delenv("FFPROBE_BINARY", raising=False)
    monkeypatch.setattr(media.shutil, "which", lambda name: None)
    calls: list[object] = []
    monkeypatch.setattr(media.subprocess, "run", lambda *a, **k: calls.append(a))
    source = _source_for_junk_video(tmp_path, monkeypatch)
    with pytest.raises(AudioUnavailable) as exc:
        source.audio_wav(0, 3, tmp_path / "a.wav")
    assert "ffmpeg" in exc.value.reason and "quá thời gian" not in exc.value.reason
    assert _probe_ffprobe(tmp_path / "clip.mp4") == {}
    assert calls == []


def test_ffmpeg_binary_tro_vao_file_khong_ton_tai_thi_bo_qua(tmp_path, monkeypatch):
    monkeypatch.setenv("FFMPEG_BINARY", str(tmp_path / "khong_co.exe"))
    monkeypatch.setattr(media.shutil, "which", lambda name: None)
    assert _decode_with_ffmpeg(tmp_path / "clip.mp4") is None
