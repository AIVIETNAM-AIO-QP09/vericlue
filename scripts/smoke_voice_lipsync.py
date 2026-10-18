"""Manual VOICE-05 smoke on one existing local recording; not an evaluation/fit.

Requires optional face/voice dependencies and local weights. No downloads, dataset
scanning, splitting, model selection or threshold changes. Media stays in output-dir.
Alignment and SyncNet weights are loaded sequentially to bound smoke-test RAM;
reported phase timings are not end-to-end API latency.
"""

from __future__ import annotations

import argparse
import dataclasses
import gc
import json
import subprocess
import time
from pathlib import Path

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.voice.align import Alignment, ForcedAligner
from vericlue_ml.voice.asr import load_audio
from vericlue_ml.voice.syncnet import SyncNetDetector

DELAY_SECONDS = 0.5
INSERTED_PAUSE_SECONDS = 1.2
SAMPLE_RATE = 16000


class _RecordedAlignments:
    """Reuse actual CTC outputs, preserving times; do not substitute synthetic scores."""

    def __init__(self, values: dict[Path, Alignment]) -> None:
        self.values = values

    def preload(self, **kwargs) -> None:
        pass

    def align(self, audio: Path, prompt: str) -> Alignment:
        return self.values[audio]


def main() -> None:
    """Print only aggregate smoke evidence; never print the prompt/transcript."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    import soundfile as sf
    import torch

    args.output_dir.mkdir(parents=True, exist_ok=True)
    prompt = args.prompt_file.read_text(encoding="utf-8")
    audio = load_audio(args.audio)
    delayed = args.output_dir / "delayed500.wav"
    spliced = args.output_dir / "spliced.wav"
    if args.audio.resolve() in {delayed.resolve(), spliced.resolve()}:
        raise ValueError("Output would overwrite the original audio")
    sf.write(
        delayed,
        np.r_[np.zeros(round(DELAY_SECONDS * SAMPLE_RATE)), audio][: len(audio)],
        SAMPLE_RATE,
    )
    middle = len(audio) // 2
    sf.write(
        spliced,
        np.r_[
            audio[:middle], np.zeros(round(INSERTED_PAUSE_SECONDS * SAMPLE_RATE)), audio[middle:]
        ],
        SAMPLE_RATE,
    )
    cases = {"original": args.audio, "spliced": spliced, "delayed500": delayed}
    report = {
        "purpose": "manual_smoke_not_evaluation",
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "device": args.device,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "audio_seconds": len(audio) / SAMPLE_RATE,
        "timing_scope": "sequential_model_phases_not_api_latency",
        "alignment": {},
        "lipsync": {},
    }
    aligner = ForcedAligner(args.models_dir)
    start = time.perf_counter()
    aligner.preload(device=args.device)
    report["ctc_preload_seconds"] = time.perf_counter() - start
    recorded = {}
    for name, path in cases.items():
        start = time.perf_counter()
        result = aligner.align(path, prompt)
        recorded[path] = result
        report["alignment"][name] = {
            "seconds": time.perf_counter() - start,
            "splice_flags": len(result.splice_events),
            "events": [dataclasses.asdict(event) for event in result.splice_events],
            "start_s": result.start_s,
            "end_s": result.end_s,
        }
        print(json.dumps({"alignment": name, **report["alignment"][name]}), flush=True)
    del aligner
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    detector = SyncNetDetector(args.models_dir, aligner=_RecordedAlignments(recorded))
    report["model_version"] = detector.version
    start = time.perf_counter()
    detector.preload(device=args.device)
    report["syncnet_scrfd_preload_seconds"] = time.perf_counter() - start
    print(
        json.dumps({"syncnet_preload_seconds": report["syncnet_scrfd_preload_seconds"]}), flush=True
    )
    for name in ("original", "delayed500"):
        result = detector.predict(
            DetectorInput(video=args.video, audio=cases[name], metadata={"prompt": prompt})
        )
        report["lipsync"][name] = result.model_dump(mode="json")
        # Do not emit the aligned prompt text to stdout/report.
        report["lipsync"][name]["evidence"] = [
            evidence
            for evidence in report["lipsync"][name]["evidence"]
            if evidence["name"] != "aligned_prompt"
        ]
        print(
            json.dumps({"lipsync": name, **report["lipsync"][name]}, ensure_ascii=True), flush=True
        )
    (args.output_dir / "smoke.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
