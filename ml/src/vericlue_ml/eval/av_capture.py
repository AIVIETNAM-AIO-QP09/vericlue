"""Windows single-input DirectShow capture to bounded RAM Matroska, never media files.

Use an installed FFmpeg executable, not copied FFmpeg code. Device enumeration:
FFmpeg n8.0 doc/indevs.texi (dshow) and libavdevice/dshow.c. PyAV 19.0.2
av.open(file-like), demux, Packet.pts/time_base/decode. One input opens both
devices in a common graph; driver latency is still unvalidated, not an attack.
"""

from __future__ import annotations

import hashlib
import math
import os
import queue
import re
import shutil
import subprocess
import threading
from contextlib import suppress
from pathlib import Path
from time import monotonic

import numpy as np

from vericlue_ml.common.av_recording import AVRecording, EncodedVideoFrame
from vericlue_ml.eval.microphone import MAX_RECORD_SECONDS, RecordingError

MAX_AV_BYTES = 64 * 1024 * 1024
MAX_FRAMES = MAX_RECORD_SECONDS * 60
MAX_JPEG_BYTES = 512 * 1024
MAX_AUDIO_PTS_ERROR = 0.002  # Matroska millisecond quantization, not a liveness threshold.
IS_WINDOWS = os.name == "nt"


def ffmpeg_path(path: Path | None = None) -> Path:
    selected = str(path) if path is not None else shutil.which("ffmpeg")
    if not selected:
        raise RecordingError("Install a local FFmpeg executable")
    resolved = Path(selected).resolve()
    if not resolved.is_file() or resolved.suffix.lower() in {".bat", ".cmd", ".ps1"}:
        raise RecordingError("Select an executable, not a shell script")
    return resolved


def list_devices(binary: Path) -> dict[str, list[str]]:
    """Enumerate DirectShow names only; do not start camera or microphone recording."""
    if not IS_WINDOWS:
        raise RecordingError("DirectShow capture is Windows-only")
    result = subprocess.run(
        [
            str(ffmpeg_path(binary)),
            "-hide_banner",
            "-list_devices",
            "true",
            "-f",
            "dshow",
            "-i",
            "dummy",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=10,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if len(result.stderr) > 256 * 1024:
        raise RecordingError("Device listing too large")
    devices = {"video": [], "audio": []}
    for name, kind in re.findall(
        r'"([^"\r\n]+)" \((video|audio)\)', result.stderr.decode("utf-8", errors="replace")
    ):
        if name not in devices[kind]:
            devices[kind].append(name)
    if not all(devices.values()):
        raise RecordingError("No available camera/microphone pair")
    return devices


def _device(value: str) -> str:
    if (
        not isinstance(value, str)
        or not 0 < len(value) <= 1024
        or any(c in value for c in "\0\r\n")
    ):
        raise RecordingError("Invalid DirectShow device name")
    # FFmpeg token quoting, not shell escaping. The entire input stays one argv item.
    return "'" + value.replace("'", "'\\''") + "'"


def capture_args(binary: Path, video: str, audio: str) -> list[str]:
    return [
        str(ffmpeg_path(binary)),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-rtbufsize",
        "64M",
        "-f",
        "dshow",
        "-i",
        f"video={_device(video)}:audio={_device(audio)}",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-copyts",
        "-start_at_zero",
        "-vf",
        "scale=640:480:force_original_aspect_ratio=decrease:force_divisible_by=2",
        "-c:v",
        "mjpeg",
        "-q:v",
        "3",
        "-pix_fmt",
        "yuvj420p",
        "-threads",
        "2",
        "-fps_mode",
        "passthrough",
        "-c:a",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-t",
        str(MAX_RECORD_SECONDS),
        "-flush_packets",
        "1",
        "-f",
        "matroska",
        "pipe:1",
    ]


class BoundedReader:
    """Non-seekable local pipe; constrain encoded bytes before passing them to PyAV."""

    def __init__(self, source):
        self.source, self.size = source, 0
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        if size < 0:
            size = 32768
        block = self.source.read(min(size, MAX_AV_BYTES - self.size + 1))
        self.size += len(block)
        if self.size > MAX_AV_BYTES:
            raise RecordingError("A/V byte budget exceeded")
        self.digest.update(block)
        return block

    def readable(self):
        return True


def read_av(
    source, *, started=lambda: None, preview=lambda image: None, av_module=None
) -> AVRecording:
    """Preserve cross-track PTS offsets; never reset each track to its own start."""
    if av_module is None:
        import av as av_module
    reader = BoundedReader(source)
    frames, chunks = [], []
    first_audio = None
    audio_samples = 0
    previous_video = None
    ready = False
    container = None
    recording = None
    success = False
    try:
        container = av_module.open(reader, mode="r", format="matroska")
        streams = list(container.streams)
        if len(streams) != 2 or sorted(s.type for s in streams) != ["audio", "video"]:
            raise RecordingError("Expected one audio and one video track")
        for stream in streams:
            codec = stream.codec_context
            if stream.type == "video" and (
                codec.name != "mjpeg" or not 0 < codec.width <= 640 or not 0 < codec.height <= 480
            ):
                raise RecordingError("Expected bounded MJPEG video")
            if stream.type == "audio" and (
                codec.name != "pcm_s16le" or codec.sample_rate != 16000 or codec.channels != 1
            ):
                raise RecordingError("Expected mono PCM16/16 kHz")
        for packet in container.demux():
            if packet.size == 0:
                continue
            if packet.pts is None or packet.time_base is None:
                raise RecordingError("Missing presentation timestamp")
            at_s = float(packet.pts * packet.time_base)
            if not math.isfinite(at_s):
                raise RecordingError("Nonfinite presentation timestamp")
            raw = bytes(packet)
            if packet.stream.type == "audio":
                if not raw or len(raw) % 2 or len(raw) > 16000 * 2:
                    raise RecordingError("Invalid PCM packet")
                if first_audio is None:
                    first_audio = at_s
                if abs(at_s - first_audio - audio_samples / 16000) > MAX_AUDIO_PTS_ERROR:
                    raise RecordingError("Discontinuous audio timestamps")
                pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
                chunks.append(pcm)
                audio_samples += len(pcm)
                if audio_samples > (MAX_RECORD_SECONDS + 1) * 16000:
                    raise RecordingError("Audio duration budget exceeded")
            else:
                if len(frames) >= MAX_FRAMES or not 0 < len(raw) <= MAX_JPEG_BYTES:
                    raise RecordingError("Video budget exceeded")
                if previous_video is not None and not 0 < at_s - previous_video <= 1:
                    raise RecordingError("Nonmonotonic or stalled video")
                previous_video = at_s
                decoded = list(packet.decode())
                if len(decoded) != 1:
                    raise RecordingError("Expected one JPEG frame per packet")
                image = decoded[0].to_ndarray(format="bgr24")
                if (
                    image.dtype != np.uint8
                    or image.ndim != 3
                    or image.shape[2] != 3
                    or image.shape[0] > 480
                    or image.shape[1] > 640
                ):
                    raise RecordingError("Invalid preview frame")
                frames.append(EncodedVideoFrame(at_s, bytearray(raw)))
                preview(image)
            if frames and first_audio is not None:
                if abs(at_s - first_audio) > MAX_RECORD_SECONDS + 2:
                    raise RecordingError("A/V timestamp duration exceeded")
                if not ready:
                    started()
                    ready = True
        if not frames or not chunks:
            raise RecordingError("Missing A/V data")
        for frame in frames:
            frame.at_s -= first_audio
            if not -2 <= frame.at_s <= MAX_RECORD_SECONDS + 2:
                raise RecordingError("Video is outside the original audio clock")
        recording = AVRecording(
            np.concatenate(chunks),
            16000,
            frames,
            {
                "clock": "single_container_pts_audio_origin_v1",
                "hardware_sync_verified": False,
                "video_codec": "mjpeg",
                "audio_codec": "pcm_s16le",
                "container_sha256": reader.digest.hexdigest(),
                "container_bytes": reader.size,
                "audio_origin_pts_s": first_audio,
                "first_video_relative_s": frames[0].at_s,
                "video_frames": len(frames),
                "audio_pts_tolerance_s": MAX_AUDIO_PTS_ERROR,
            },
        )
        success = True
        return recording
    finally:
        try:
            if container is not None:
                container.close()
        except Exception:
            if recording is not None:
                recording.wipe()
            raise
        finally:
            for chunk in chunks:
                chunk.fill(0)
            if not success:
                for frame in frames:
                    frame.jpeg[:] = b"\0" * len(frame.jpeg)
                frames.clear()


class AVRecorder:
    """Called only from the record worker; stop/cancel asks FFmpeg to finish, watchdog kills hangs."""

    owns_process = True

    def __init__(self, binary: Path) -> None:
        self.binary = ffmpeg_path(binary)
        self.video = self.audio = ""
        self.preview = queue.Queue(maxsize=1)

    def _preview(self, image):
        with suppress(queue.Empty):
            self.preview.get_nowait()
        self.preview.put_nowait(image)

    def __call__(self, stop, *, device=None, started=lambda: None):
        if stop.is_set() or not IS_WINDOWS:
            raise RecordingError("Capture cancelled or not Windows")
        args = capture_args(self.binary, self.video, self.audio)
        process = None
        done, forced = threading.Event(), threading.Event()
        monitor = None
        recording = None
        try:
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            def watch():
                deadline = monotonic() + MAX_RECORD_SECONDS + 10
                stopping = None
                while not done.wait(0.05):
                    if stop.is_set() and stopping is None:
                        stopping = monotonic()
                        try:
                            process.stdin.write(b"q\n")
                            process.stdin.flush()
                        except (OSError, ValueError):
                            pass
                    if monotonic() >= deadline or (
                        stopping is not None and monotonic() - stopping >= 3
                    ):
                        forced.set()
                        with suppress(OSError):
                            process.kill()
                        return

            monitor = threading.Thread(target=watch, daemon=False)
            monitor.start()
            recording = read_av(process.stdout, started=started, preview=self._preview)
            recording.metadata["capture_backend"] = "ffmpeg_directshow_single_input"
            process.wait(timeout=5)
            if process.returncode != 0 or forced.is_set():
                raise RecordingError("Incomplete A/V capture")
            return recording
        except Exception as exc:
            if recording is not None:
                recording.wipe()
            raise RecordingError("Cannot capture complete A/V") from exc
        finally:
            done.set()
            cleanup_failed = False
            if process is not None:
                try:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    cleanup_failed = True
                finally:
                    with suppress(OSError, ValueError):
                        process.stdin.close()
                    with suppress(OSError, ValueError):
                        process.stdout.close()
            if monitor is not None:
                monitor.join(timeout=1)
            if cleanup_failed:
                if recording is not None:
                    recording.wipe()
                raise RecordingError("Cannot finish cleanup of owned capture process")
