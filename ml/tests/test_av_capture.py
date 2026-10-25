"""Single-container clock/budget/process tests without PyAV, FFmpeg or real devices."""

import io
import threading
from fractions import Fraction
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.av_recording import AVRecording, EncodedVideoFrame
from vericlue_ml.eval import av_capture as cap


class Packet:
    def __init__(self, kind, at, raw=None):
        self.stream = SimpleNamespace(type=kind)
        self.pts = round(at * 1000)
        self.time_base = Fraction(1, 1000)
        self.raw = raw if raw is not None else (b"jpeg" if kind == "video" else b"\0\0" * 320)
        self.size = len(self.raw)

    def __bytes__(self):
        return self.raw

    def decode(self):
        return [SimpleNamespace(to_ndarray=lambda **kw: np.zeros((24, 32, 3), np.uint8))]


class Container:
    def __init__(self, packets):
        self.packets = packets
        self.closed = False
        self.streams = [
            SimpleNamespace(
                type="video", codec_context=SimpleNamespace(name="mjpeg", width=32, height=24)
            ),
            SimpleNamespace(
                type="audio",
                codec_context=SimpleNamespace(name="pcm_s16le", sample_rate=16000, channels=1),
            ),
        ]

    def demux(self):
        return iter(self.packets)

    def close(self):
        self.closed = True


def parse(container, **kwargs):
    def open_container(reader, **options):
        assert options == {"mode": "r", "format": "matroska"}
        reader.read(100)
        return container

    return cap.read_av(
        io.BytesIO(b"unit-container"), av_module=SimpleNamespace(open=open_container), **kwargs
    )


def test_common_audio_origin_preserves_video_preroll_without_independent_track_reset():
    container = Container(
        [Packet("video", 9.8), Packet("audio", 10), Packet("video", 10.02), Packet("audio", 10.02)]
    )
    ready, previews = [], []
    recording = parse(container, started=lambda: ready.append(True), preview=previews.append)
    assert container.closed and ready == [True] and len(previews) == 2
    assert [frame.at_s for frame in recording.frames] == pytest.approx([-0.2, 0.02])
    assert recording.metadata["audio_origin_pts_s"] == 10
    assert recording.samples.shape == (640,) and recording.samples.dtype == np.float32
    checksum = recording.video_sha256()
    recording.frames[0].at_s += 0.01
    assert recording.video_sha256() != checksum
    reference = recording.frames[0].jpeg
    recording.wipe()
    assert not recording.frames and not any(reference) and not recording.samples.any()


@pytest.mark.parametrize(
    "change",
    [
        "missing_pts",
        "video_backwards",
        "audio_gap",
        "audio_overlap",
        "bad_codec",
        "stereo",
        "too_large",
        "missing_track",
        "no_audio",
    ],
)
def test_invalid_or_incomplete_capture_cannot_be_scored(change):
    packets = [Packet("video", 0), Packet("audio", 0), Packet("video", 0.04), Packet("audio", 0.02)]
    container = Container(packets)
    if change == "missing_pts":
        packets[0].pts = None
    if change == "video_backwards":
        packets[2].pts = -1
    if change == "audio_gap":
        packets[3].pts = 40
    if change == "audio_overlap":
        packets[3].pts = 0
    if change == "bad_codec":
        container.streams[0].codec_context.name = "h264"
    if change == "stereo":
        container.streams[1].codec_context.channels = 2
    if change == "too_large":
        container.streams[0].codec_context.width = 8192
    if change == "missing_track":
        container.streams.pop()
    if change == "no_audio":
        container.packets = [Packet("video", 0)]
    with pytest.raises(cap.RecordingError):
        parse(container)
    assert container.closed


def test_byte_and_frame_budgets_are_enforced(monkeypatch):
    monkeypatch.setattr(cap, "MAX_AV_BYTES", 4)
    with pytest.raises(cap.RecordingError):
        cap.BoundedReader(io.BytesIO(b"12345")).read(100)
    monkeypatch.setattr(cap, "MAX_AV_BYTES", 100)
    monkeypatch.setattr(cap, "MAX_FRAMES", 1)
    with pytest.raises(cap.RecordingError):
        parse(Container([Packet("video", 0), Packet("audio", 0), Packet("video", 0.04)]))


def test_dshow_arguments_keep_both_devices_in_one_input_and_use_no_shell(tmp_path):
    binary = tmp_path / "ffmpeg.exe"
    binary.write_bytes(b"unit")
    args = cap.capture_args(binary, "Camera: test's $(anything)", "Microphone & test")
    assert args.count("-i") == 1 and args[-1] == "pipe:1"
    source = args[args.index("-i") + 1]
    assert "video=" in source and ":audio=" in source and "$(anything)" in source
    assert "q" not in args and "-copyts" in args and "-start_at_zero" in args
    with pytest.raises(cap.RecordingError):
        cap.capture_args(binary, "bad\nname", "mic")
    script = tmp_path / "ffmpeg.cmd"
    script.write_bytes(b"unit")
    with pytest.raises(cap.RecordingError):
        cap.ffmpeg_path(script)


def test_device_listing_does_not_record_and_parses_only_friendly_names(tmp_path, monkeypatch):
    binary = tmp_path / "ffmpeg.exe"
    binary.write_bytes(b"unit")
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            stderr=b'[dshow] "Camera" (video)\n[dshow] Alternative name "private-id"\n[dshow] "Mic" (audio)'
        )

    monkeypatch.setattr(cap, "IS_WINDOWS", True)
    monkeypatch.setattr(cap.subprocess, "run", run)
    assert cap.list_devices(binary) == {"video": ["Camera"], "audio": ["Mic"]}
    assert "-list_devices" in calls[0][0] and calls[0][0][-1] == "dummy"
    assert calls[0][1]["shell"] is False and calls[0][1]["timeout"] == 10


class Sink:
    def __init__(self):
        self.asked_stop = threading.Event()
        self.closed = False

    def write(self, data):
        assert data == b"q\n"
        self.asked_stop.set()

    def flush(self):
        pass

    def close(self):
        self.closed = True


class Process:
    def __init__(self, code=0):
        self.stdin, self.stdout = Sink(), io.BytesIO()
        self.returncode = None
        self.code = code
        self.killed = False

    def wait(self, timeout=None):
        self.returncode = self.code
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


@pytest.mark.parametrize("broken", [False, True])
def test_stop_flushes_and_closes_owned_process_and_failure_wipes_media(
    tmp_path, monkeypatch, broken
):
    binary = tmp_path / "ffmpeg.exe"
    binary.write_bytes(b"unit")
    process = Process(1 if broken else 0)
    calls = []

    def spawn(args, **kwargs):
        calls.append(kwargs)
        return process

    monkeypatch.setattr(cap, "IS_WINDOWS", True)
    monkeypatch.setattr(cap.subprocess, "Popen", spawn)
    stop = threading.Event()
    recording = AVRecording(
        np.ones(320, np.float32), 16000, [EncodedVideoFrame(0, bytearray(b"jpeg"))]
    )

    def read(*args, **kwargs):
        kwargs["started"]()
        stop.set()
        assert process.stdin.asked_stop.wait(2)
        return recording

    monkeypatch.setattr(cap, "read_av", read)
    recorder = cap.AVRecorder(binary)
    recorder.video, recorder.audio = "camera", "mic"
    ready = []
    if broken:
        with pytest.raises(cap.RecordingError):
            recorder(stop, started=lambda: ready.append(True))
        assert not recording.samples.any() and not recording.frames
    else:
        assert recorder(stop, started=lambda: ready.append(True)) is recording
    assert ready == [True] and process.stdin.closed and process.stdout.closed
    assert calls[0]["shell"] is False


def test_pre_cancel_never_opens_devices(tmp_path, monkeypatch):
    binary = tmp_path / "ffmpeg.exe"
    binary.write_bytes(b"unit")
    monkeypatch.setattr(cap.subprocess, "Popen", lambda *a, **kw: pytest.fail("must not open"))
    stop = threading.Event()
    stop.set()
    with pytest.raises(cap.RecordingError):
        cap.AVRecorder(binary)(stop)


def test_container_close_failure_wipes_the_assembled_take(monkeypatch):
    saved = []
    original = cap.AVRecording

    def make(*args, **kwargs):
        value = original(*args, **kwargs)
        saved.append(value)
        return value

    monkeypatch.setattr(cap, "AVRecording", make)
    container = Container([Packet("video", 0), Packet("audio", 0, b"\1\0" * 320)])

    def close():
        raise RuntimeError("close failed")

    container.close = close
    with pytest.raises(RuntimeError):
        parse(container)
    assert len(saved) == 1 and not saved[0].samples.any() and not saved[0].frames


def test_watchdog_rejects_buffered_media_after_forced_kill(tmp_path, monkeypatch):
    binary = tmp_path / "ffmpeg.exe"
    binary.write_bytes(b"unit")
    process = Process()
    killed = threading.Event()
    original = process.kill

    def kill():
        original()
        killed.set()

    process.kill = kill
    monkeypatch.setattr(cap, "IS_WINDOWS", True)
    monkeypatch.setattr(cap.subprocess, "Popen", lambda *a, **kw: process)
    ticks = iter([0.0, 31.0])
    monkeypatch.setattr(cap, "monotonic", lambda: next(ticks))
    take = AVRecording(np.ones(320, np.float32), 16000, [EncodedVideoFrame(0, bytearray(b"jpeg"))])

    def read(*a, **kw):
        assert killed.wait(2)
        return take

    monkeypatch.setattr(cap, "read_av", read)
    recorder = cap.AVRecorder(binary)
    recorder.video, recorder.audio = "camera", "mic"
    with pytest.raises(cap.RecordingError):
        recorder(threading.Event())
    assert process.killed and not take.frames and not take.samples.any()
    assert process.stdin.closed and process.stdout.closed
