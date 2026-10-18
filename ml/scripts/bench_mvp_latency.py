"""Đo thời gian (p50/p95) và VRAM của các detector MVP — THỬ TAY, không phải kết quả R6.

Đo trên máy chạy script: `quality`, `face_pad`, `face_deepfake` (GenD, 8 khung từ video), `voice_spoof`
(audio 4–6 s) và `voice_challenge`. Mỗi mô hình nạp một lần, chạy `--warmup` lần khởi động rồi `--runs`
lần đo. Ghi VRAM toàn GPU sau từng lần nạp (cùng một tiến trình) và đỉnh khi chạy. Dữ liệu đầu vào lấy
từ kho dữ liệu cục bộ (khung từ video Zalo 2022 làm "ảnh điện thoại", audio VIVOS 4–6 s kèm câu đọc);
đây chỉ là tải giả để đo tốc độ, KHÔNG dùng để đánh giá độ chính xác hay chọn ngưỡng.

Ví dụ (GPU):
    $env:UV_PROJECT_ENVIRONMENT=".venv-gpu"
    uv run --no-sync python ml/scripts/bench_mvp_latency.py --device cuda --out tmp/bench-gpu.json
So sánh CPU/GPU (độ lệch điểm, không phải độ chính xác): chạy lại với `--device cpu` rồi so `samples`.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DEFAULT_DATA = Path(r"D:\Projects\vericlue-store\data")
DEFAULT_MODELS = Path(r"D:\Projects\vericlue-store\models")


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[index]


def summarize(ms: list[float]) -> dict[str, float]:
    return {
        "n": len(ms),
        "p50_ms": round(percentile(ms, 0.5), 1),
        "p95_ms": round(percentile(ms, 0.95), 1),
        "min_ms": round(min(ms), 1),
        "max_ms": round(max(ms), 1),
        "mean_ms": round(statistics.fmean(ms), 1),
    }


class Vram:
    """VRAM dùng của TOÀN GPU (mọi tiến trình), lấy từ trình điều khiển qua torch.cuda.mem_get_info."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.peak = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def used_mb(self) -> float:
        if not self.enabled:
            return 0.0
        import torch

        free, total = torch.cuda.mem_get_info()
        return (total - free) / 2**20

    def start(self) -> None:
        if not self.enabled:
            return

        def poll() -> None:
            while not self._stop.is_set():
                self.peak = max(self.peak, self.used_mb())
                time.sleep(0.02)

        self._stop.clear()
        self._thread = threading.Thread(target=poll, daemon=True)
        self._thread.start()

    def stop(self) -> float:
        if self._thread is not None:
            self._stop.set()
            self._thread.join()
            self._thread = None
        return self.peak

    def reset(self) -> None:
        self.peak = self.used_mb()


def build_inputs(data: Path, workdir: Path, count: int):
    """Ảnh (khung giữa video Zalo), video Zalo và audio VIVOS 4–6 s kèm câu đọc."""
    import cv2
    import soundfile as sf

    zalo = data / "raw" / "zalo2022" / "train" / "train"
    with (zalo / "label.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    videos = [zalo / "videos" / r["fname"] for r in rows[:: max(1, len(rows) // (count * 2))]]
    images, clips = [], []
    for video in videos:
        capture = cv2.VideoCapture(str(video))
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, total // 2))
        ok, frame = capture.read()
        capture.release()
        if ok:
            path = workdir / f"img{len(images):02d}.png"
            cv2.imwrite(str(path), frame)
            images.append(path)
            clips.append(video)
        if len(images) == count:
            break
    vivos = data / "raw" / "vivos" / "vivos" / "test"
    prompts = {}
    for line in (vivos / "prompts.txt").read_text(encoding="utf-8").splitlines():
        key, _, text = line.partition(" ")
        prompts[key] = text
    audio = []
    for key, text in prompts.items():
        wav = vivos / "waves" / key.split("_")[0] / f"{key}.wav"
        if wav.is_file() and 4.0 <= sf.info(str(wav)).duration <= 6.0:
            audio.append((wav, text))
        if len(audio) == count:
            break
    return images, clips, audio


def timed(fn, warmup: int, runs: int, items: list, vram: Vram):
    """Chạy `fn(item)` luân phiên qua `items`; trả (danh sách ms, danh sách kết quả của lần đo)."""
    for index in range(warmup):
        fn(items[index % len(items)])
    vram.reset()
    vram.start()
    ms, outputs = [], []
    for index in range(runs):
        item = items[index % len(items)]
        started = time.perf_counter()
        outputs.append(fn(item))
        ms.append((time.perf_counter() - started) * 1000)
    vram.stop()
    return ms, outputs


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--device", default="cuda", help="cpu | cuda | auto")
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--samples", type=int, default=8, help="số mẫu đầu vào luân phiên")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    import torch

    from vericlue_ml.common.detector import DetectorInput
    from vericlue_ml.face.gend import FaceDeepfakeDetector
    from vericlue_ml.face.pad import FacePadDetector
    from vericlue_ml.face.quality import QualityDetector
    from vericlue_ml.voice.antispoof import AntiDeepfakeDetector
    from vericlue_ml.voice.challenge import VoiceChallengeDetector

    use_gpu = args.device != "cpu" and torch.cuda.is_available()
    vram = Vram(use_gpu)
    report: dict = {
        "device_requested": args.device,
        "gpu": torch.cuda.get_device_name(0) if use_gpu else None,
        "torch": torch.__version__,
        "platform": platform.platform(),
        "runs": args.runs,
        "warmup": args.warmup,
        "load": {},
        "latency": {},
        "samples": {},
    }
    workdir = Path(tempfile.mkdtemp(prefix="vericlue-bench-"))
    images, clips, audio = build_inputs(args.data_dir, workdir, args.samples)
    if not (images and audio):
        raise SystemExit("Không dựng được dữ liệu đo (ảnh/audio).")
    report["inputs"] = {"images": len(images), "videos": len(clips), "audio": len(audio)}

    baseline = vram.used_mb()
    report["load"]["vram_baseline_mb"] = round(baseline, 0)
    detectors = {
        "face_pad": FacePadDetector(),
        "quality": QualityDetector(),
        "face_deepfake": FaceDeepfakeDetector(),
        "voice_spoof": AntiDeepfakeDetector(),
        "voice_challenge": VoiceChallengeDetector(),
    }
    for name, detector in detectors.items():
        started = time.perf_counter()
        detector.preload(models_dir=args.models_dir, device=args.device)
        report["load"][name] = {
            "seconds": round(time.perf_counter() - started, 1),
            "vram_used_after_mb": round(vram.used_mb(), 0),
        }
    report["load"]["vram_all_loaded_mb"] = round(vram.used_mb(), 0)
    report["load"]["vram_added_by_models_mb"] = round(vram.used_mb() - baseline, 0)
    report["load"]["vram_total_mb"] = (
        round(torch.cuda.mem_get_info()[1] / 2**20, 0) if use_gpu else None
    )

    def img_input(path):
        return DetectorInput(images=[path])

    def vid_input(path):
        return DetectorInput(video=path)

    def audio_input(item):
        return DetectorInput(audio=item[0])

    def challenge_input(item):
        return DetectorInput(audio=item[0], metadata={"prompt": item[1]})

    plan = [
        ("quality", detectors["quality"], images, img_input),
        ("face_pad", detectors["face_pad"], images, img_input),
        ("face_deepfake_8_frames", detectors["face_deepfake"], clips, vid_input),
        ("voice_spoof", detectors["voice_spoof"], audio, audio_input),
        ("voice_challenge", detectors["voice_challenge"], audio, challenge_input),
    ]
    for name, detector, items, make in plan:
        ms, outputs = timed(
            lambda item, d=detector, m=make: d.predict(m(item)),
            args.warmup,
            args.runs,
            items,
            vram,
        )
        statuses = sorted({str(o.status) for o in outputs})
        report["latency"][name] = {
            **summarize(ms),
            "status": statuses,
            "vram_peak_mb": round(vram.peak, 0),
        }
        report["samples"][name] = [
            {"score": o.score, "gate": o.gate, "status": str(o.status)}
            for o in outputs[: len(items)]
        ]

    # Chuỗi khuôn mặt giống orchestrator: quality + face_pad + GenD (tuần tự và song song).
    face = [
        (detectors["quality"], img_input),
        (detectors["face_pad"], img_input),
        (detectors["face_deepfake"], vid_input),
    ]

    def face_sequential(index: int):
        for detector, make in face:
            source = clips if detector is detectors["face_deepfake"] else images
            detector.predict(make(source[index % len(source)]))

    pool = ThreadPoolExecutor(max_workers=3)

    def face_parallel(index: int):
        futures = []
        for detector, make in face:
            source = clips if detector is detectors["face_deepfake"] else images
            futures.append(pool.submit(detector.predict, make(source[index % len(source)])))
        for future in futures:
            future.result()

    for name, fn in (
        ("face_chain_sequential", face_sequential),
        ("face_chain_parallel", face_parallel),
    ):
        ms, _ = timed(fn, args.warmup, args.runs, list(range(len(images))), vram)
        report["latency"][name] = {**summarize(ms), "vram_peak_mb": round(vram.peak, 0)}
    pool.shutdown()

    report["load"]["vram_peak_whole_run_mb"] = round(
        max(v.get("vram_peak_mb", 0) for v in report["latency"].values()), 0
    )
    try:
        report["nvidia_smi"] = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        report["nvidia_smi"] = None

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
