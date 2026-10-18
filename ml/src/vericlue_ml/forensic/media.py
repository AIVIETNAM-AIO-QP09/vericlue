"""FOR-01 — đọc metadata và cắt khung/âm thanh theo đoạn cho giám định.

Chọn công cụ (chạy được trên Windows, không cần cài ffmpeg riêng):
- **ffprobe không có trên PATH** của máy dev Windows, nên KHÔNG dùng.
- **Hình + metadata video:** `cv2.VideoCapture` (opencv-python-headless, đã nằm trong extra `face`):
  fps, số khung, độ phân giải, mã FourCC; tìm khung theo chỉ số.
- **Âm thanh trong file âm thanh** (wav/flac/ogg/mp3): `soundfile` (extra `voice`).
- **Âm thanh trong video** (mp4/webm/mov) và metadata cấp container, theo thứ tự thử: PyAV (`av`) nếu
  môi trường đã cài, rồi `ffmpeg`/`ffprobe` trên PATH (hoặc biến FFMPEG_BINARY/FFPROBE_BINARY) gọi
  bằng subprocess. **Cả hai đều tùy chọn và KHÔNG khai báo làm dependency**: wheel PyAV đóng gói FFmpeg
  mà giấy phép (LGPL hay GPL) chưa xác nhận, nên không kéo vào dự án (AGENTS.md luật 6); ffmpeg do
  người vận hành tự cài, không phân phối kèm. Không có công cụ nào thì không giải mã được tiếng của
  video: `has_audio` là None và bước giọng nói được báo `unavailable` với lý do rõ ràng. Không tự đoán.

SHA-256 do bên gọi tính trên byte gốc TRƯỚC khi gọi các hàm ở đây; các hàm này không ghi vào file nguồn.
Mọi import nặng nằm trong hàm để gói vẫn import được khi thiếu extra (test thuần không cần cv2).
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import shutil
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np

TARGET_SAMPLE_RATE = 16000


class MediaError(Exception):
    """File không đọc được hoặc định dạng chưa hỗ trợ (có mã ngắn để báo lên job)."""

    def __init__(self, message: str, code: str = "unsupported_media") -> None:
        super().__init__(message)
        self.code = code


class AudioUnavailable(Exception):
    """Không có tiếng hoặc không giải mã được; `reason` là câu tiếng Việt cho người dùng."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class MediaInfo:
    kind: Literal["video", "audio"]
    size_bytes: int
    duration_s: float | None = None
    container: str | None = None
    video_codec: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    bitrate_kbps: float | None = None
    has_audio: bool | None = None  # None = chưa biết (thiếu công cụ giải mã)
    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = {k: v for k, v in self.__dict__.items() if k != "notes"}
        return data


class MediaSource(Protocol):
    """Nguồn media đã mở. Bản thật: `FileMediaSource`; test dùng bản giả."""

    info: MediaInfo

    def frames(self, t0: float, t1: float, count: int, outdir: Path) -> list[Path]:
        """Tối đa `count` khung PNG cách đều trong [t0, t1); rỗng nếu không đọc được khung nào."""
        ...

    def audio_wav(self, t0: float, t1: float, out: Path) -> Path:
        """Ghi âm thanh [t0, t1) thành WAV 16 kHz mono; ném AudioUnavailable nếu không có tiếng."""
        ...

    def full_audio_wav(self, out: Path) -> Path:
        """Toàn bộ âm thanh (cho AudioSeal); ném AudioUnavailable nếu không có."""
        ...


def _write_wav(path: Path, samples: np.ndarray, rate: int = TARGET_SAMPLE_RATE) -> Path:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())
    return path


def _to_mono16k(data: np.ndarray, rate: int) -> np.ndarray:
    mono = data.mean(axis=1) if data.ndim == 2 else data
    mono = mono.astype("float32", copy=False)
    if rate == TARGET_SAMPLE_RATE:
        return mono
    from scipy.signal import resample_poly

    g = math.gcd(TARGET_SAMPLE_RATE, rate)
    return resample_poly(mono, TARGET_SAMPLE_RATE // g, rate // g).astype("float32")


def _decode_with_soundfile(path: Path) -> np.ndarray | None:
    try:
        import soundfile
    except ImportError:
        return None
    try:
        data, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
    except Exception:  # noqa: BLE001 — định dạng soundfile không đọc được (mp4, aac...)
        return None
    return _to_mono16k(data, int(rate))


def _decode_with_wave(path: Path) -> np.ndarray | None:
    """WAV PCM bằng thư viện chuẩn `wave` (không cần soundfile). None nếu không phải WAV PCM đọc được."""
    try:
        with wave.open(str(path), "rb") as handle:
            channels, width, rate = (
                handle.getnchannels(),
                handle.getsampwidth(),
                handle.getframerate(),
            )
            raw = handle.readframes(handle.getnframes())
    except (wave.Error, EOFError, OSError):
        return None
    if channels < 1 or rate < 1 or width not in (1, 2, 3, 4):
        return None
    usable = len(raw) // (width * channels) * (width * channels)
    raw = raw[:usable]
    if width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype("float32") - 128.0) / 128.0
    elif width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype("int32")
        value = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        value = np.where(value >= 1 << 23, value - (1 << 24), value)
        data = value.astype("float32") / float(1 << 23)
    else:
        data = np.frombuffer(raw, dtype="<i4").astype("float32") / float(1 << 31)
    return _to_mono16k(data.reshape(-1, channels), rate)


def _decode_audio_file(path: Path) -> np.ndarray | None:
    """File âm thanh (WAV/FLAC/OGG/MP3) → mono 16 kHz: soundfile nếu có, không thì `wave` cho WAV PCM."""
    samples = _decode_with_soundfile(path)
    return samples if samples is not None else _decode_with_wave(path)


def _probe_wave(path: Path) -> tuple[float, int] | None:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            return handle.getnframes() / rate, rate
    except (wave.Error, EOFError, OSError, ZeroDivisionError):
        return None


def _decode_with_av(path: Path) -> np.ndarray | None:
    """Giải mã mọi âm thanh trong container bằng PyAV; None nếu thiếu PyAV hoặc không có luồng tiếng."""
    try:
        import av
    except ImportError:
        return None
    try:
        with av.open(str(path)) as container:
            if not container.streams.audio:
                return np.zeros(0, dtype="float32")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=TARGET_SAMPLE_RATE)
            chunks: list[np.ndarray] = []
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    chunks.append(out.to_ndarray().reshape(-1))
            for out in resampler.resample(None):
                chunks.append(out.to_ndarray().reshape(-1))
    except Exception:  # noqa: BLE001
        return None
    if not chunks:
        return np.zeros(0, dtype="float32")
    return np.concatenate(chunks).astype("float32") / 32768.0


FFMPEG_TIMEOUT_SECONDS = 120


def _tool(env_name: str, default: str) -> str | None:
    """Đường dẫn ffmpeg/ffprobe: biến môi trường rồi PATH; None nếu không có."""
    configured = os.environ.get(env_name)
    if configured and Path(configured).is_file():
        return configured
    return shutil.which(default)


def _decode_with_ffmpeg(path: Path) -> np.ndarray | None:
    """Giải mã tiếng bằng ffmpeg (subprocess, tham số dạng danh sách, không qua shell). None nếu không có
    ffmpeg; mảng rỗng nếu file không có luồng tiếng."""
    exe = _tool("FFMPEG_BINARY", "ffmpeg")
    if exe is None:
        return None
    command = [
        exe,
        "-v",
        "error",
        "-nostdin",
        "-protocol_whitelist",  # file tải lên có thể là danh sách phát trỏ tới URL/file khác
        "file,pipe",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-f",
        "s16le",
        "-",
    ]
    try:
        done = subprocess.run(
            command, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioUnavailable("ffmpeg giải mã âm thanh quá thời gian cho phép.") from exc
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0 and not done.stdout:
        # ffmpeg báo lỗi mà không ra mẫu nào: coi như không giải mã được (hoặc không có tiếng).
        return np.zeros(0, dtype="float32")
    pcm = np.frombuffer(done.stdout[: len(done.stdout) // 2 * 2], dtype="<i2")
    return pcm.astype("float32") / 32768.0


def _probe_ffprobe(path: Path) -> dict[str, Any]:
    exe = _tool("FFPROBE_BINARY", "ffprobe")
    if exe is None:
        return {}
    command = [
        exe,
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    try:
        done = subprocess.run(command, capture_output=True, timeout=30, check=False)
        data = json.loads(done.stdout or b"{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}
    info: dict[str, Any] = {}
    fmt = data.get("format") or {}
    if fmt.get("format_name"):
        info["container"] = str(fmt["format_name"]).split(",")[0]
    if fmt.get("duration"):
        with contextlib.suppress(ValueError):
            info["duration_s"] = float(fmt["duration"])
    streams = data.get("streams") or []
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    video = [s for s in streams if s.get("codec_type") == "video"]
    info["has_audio"] = bool(audio)
    if video:
        info["video_codec"] = video[0].get("codec_name")
    if audio:
        info["audio_codec"] = audio[0].get("codec_name")
        with contextlib.suppress(ValueError):
            info["audio_sample_rate"] = int(audio[0].get("sample_rate") or 0) or None
    return info


def _probe_av(path: Path) -> dict[str, Any]:
    """Thông tin container/luồng bằng PyAV nếu có; rỗng nếu không."""
    try:
        import av
    except ImportError:
        return {}
    try:
        with av.open(str(path)) as container:
            info: dict[str, Any] = {
                "container": container.format.name,
                "has_audio": bool(container.streams.audio),
            }
            if container.duration:
                info["duration_s"] = float(container.duration) / 1_000_000.0
            if container.streams.video:
                info["video_codec"] = container.streams.video[0].codec_context.name
            if container.streams.audio:
                audio = container.streams.audio[0]
                info["audio_codec"] = audio.codec_context.name
                info["audio_sample_rate"] = int(audio.codec_context.sample_rate or 0) or None
            return info
    except Exception:  # noqa: BLE001
        return {}


def _fourcc_to_str(value: float) -> str | None:
    code = int(value)
    if code <= 0:
        return None
    text = "".join(chr((code >> (8 * i)) & 0xFF) for i in range(4))
    return text.strip().lower() if text.isprintable() and text.strip() else None


def probe_media(path: Path) -> MediaInfo:
    """Đọc thông số file (không chuyển mã). Ném MediaError nếu không phải video/âm thanh đọc được."""
    path = Path(path)
    size = path.stat().st_size
    notes: list[str] = []
    av_info = _probe_av(path) or _probe_ffprobe(path)

    video = _probe_cv2(path)
    if video is not None:
        fps, frames, width, height, codec = video
        duration = av_info.get("duration_s")
        if duration is None and fps and frames:
            duration = frames / fps
        return MediaInfo(
            kind="video",
            size_bytes=size,
            duration_s=duration,
            container=av_info.get("container") or path.suffix.lstrip(".").lower() or None,
            video_codec=av_info.get("video_codec") or codec,
            width=width,
            height=height,
            fps=fps,
            bitrate_kbps=(size * 8 / 1000 / duration) if duration else None,
            has_audio=av_info.get("has_audio"),
            audio_codec=av_info.get("audio_codec"),
            audio_sample_rate=av_info.get("audio_sample_rate"),
            notes=notes,
        )

    try:
        import soundfile

        sf = soundfile.info(str(path))
        duration = float(sf.duration)
        return MediaInfo(
            kind="audio",
            size_bytes=size,
            duration_s=duration,
            container=sf.format.lower(),
            audio_codec=sf.subtype.lower(),
            audio_sample_rate=int(sf.samplerate),
            has_audio=True,
            bitrate_kbps=(size * 8 / 1000 / duration) if duration else None,
            notes=notes,
        )
    except ImportError:
        notes.append("Thiếu soundfile (extra voice): chỉ đọc được WAV PCM bằng thư viện chuẩn.")
    except Exception:  # noqa: BLE001
        pass

    wav = _probe_wave(path)
    if wav is not None:
        duration, rate = wav
        return MediaInfo(
            kind="audio",
            size_bytes=size,
            duration_s=duration,
            container="wav",
            audio_codec="pcm",
            audio_sample_rate=int(rate),
            has_audio=True,
            bitrate_kbps=(size * 8 / 1000 / duration) if duration else None,
            notes=notes,
        )

    if av_info and "duration_s" in av_info and not av_info.get("video_codec"):
        duration = float(av_info["duration_s"])
        return MediaInfo(
            kind="audio",
            size_bytes=size,
            duration_s=duration,
            container=av_info.get("container"),
            audio_codec=av_info.get("audio_codec"),
            audio_sample_rate=av_info.get("audio_sample_rate"),
            has_audio=av_info.get("has_audio", True),
            bitrate_kbps=(size * 8 / 1000 / duration) if duration else None,
            notes=notes,
        )
    raise MediaError(
        "Không đọc được file như video hoặc âm thanh. " + " ".join(notes), "unsupported_media"
    )


def _probe_cv2(path: Path) -> tuple[float | None, int, int, int, str | None] | None:
    try:
        import cv2
    except ImportError:
        return None
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return None
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        codec = _fourcc_to_str(cap.get(cv2.CAP_PROP_FOURCC))
        if width <= 0 or height <= 0:
            return None
        if frames <= 0 or not math.isfinite(fps) or fps <= 0:
            # webm/stream có thể không khai số khung; đọc thử một khung để chắc là video.
            ok, _ = cap.read()
            if not ok:
                return None
        return (fps if fps > 0 else None), max(frames, 0), width, height, codec
    finally:
        cap.release()


class FileMediaSource:
    """Mở một file video/âm thanh thật; giải mã âm thanh một lần rồi cắt theo đoạn."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.info = probe_media(self.path)
        self._audio: np.ndarray | None = None
        self._audio_error: str | None = None

    # --- âm thanh -----------------------------------------------------------
    def _load_audio(self) -> np.ndarray:
        if self._audio is not None:
            return self._audio
        if self._audio_error is not None:
            raise AudioUnavailable(self._audio_error)
        samples = _decode_audio_file(self.path)
        if samples is None:
            samples = _decode_with_av(self.path)
        if samples is None:
            samples = _decode_with_ffmpeg(self.path)
        if samples is None:
            self._audio_error = (
                "Không giải mã được âm thanh của file này. Video (mp4, webm...) cần PyAV (`av`) hoặc "
                "ffmpeg trên PATH; chưa có nên bước giọng nói không chạy."
            )
            raise AudioUnavailable(self._audio_error)
        if samples.size == 0:
            self._audio_error = "File không có luồng âm thanh."
            raise AudioUnavailable(self._audio_error)
        self._audio = samples
        return samples

    def audio_wav(self, t0: float, t1: float, out: Path) -> Path:
        samples = self._load_audio()
        a = max(0, int(round(t0 * TARGET_SAMPLE_RATE)))
        b = min(samples.size, int(round(t1 * TARGET_SAMPLE_RATE)))
        return _write_wav(out, samples[a:b])

    def full_audio_wav(self, out: Path) -> Path:
        return _write_wav(out, self._load_audio())

    # --- hình ---------------------------------------------------------------
    def frames(self, t0: float, t1: float, count: int, outdir: Path) -> list[Path]:
        if self.info.kind != "video" or count <= 0 or t1 <= t0:
            return []
        import cv2

        fps = self.info.fps or 25.0
        first = max(0, int(round(t0 * fps)))
        last = max(first, int(round(t1 * fps)) - 1)
        if count == 1:
            wanted = [(first + last) // 2]
        else:
            wanted = sorted({int(round(x)) for x in np.linspace(first, last, count)})
        outdir.mkdir(parents=True, exist_ok=True)
        cap = cv2.VideoCapture(str(self.path))
        paths: list[Path] = []
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, wanted[0])
            index = wanted[0]
            targets = iter(wanted)
            target = next(targets)
            while True:
                ok = cap.grab()
                if not ok:
                    break
                if index == target:
                    ok, frame = cap.retrieve()
                    if ok:
                        path = outdir / f"f{index:07d}.png"
                        cv2.imwrite(str(path), frame)
                        paths.append(path)
                    try:
                        target = next(targets)
                    except StopIteration:
                        break
                index += 1
        finally:
            cap.release()
        return paths
