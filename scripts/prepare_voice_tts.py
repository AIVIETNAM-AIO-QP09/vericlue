"""Prepare fixed Vietnamese TTS fixtures; never part of production inference."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import httpx

from vericlue_ml.voice.phrases import PROMPTS

ESPEAK_VERSION = "1.52.0"
ESPEAK_URL = (
    f"https://github.com/espeak-ng/espeak-ng/releases/download/{ESPEAK_VERSION}/espeak-ng.msi"
)
ESPEAK_BYTES = 12_765_862


def prepare_tool(root: Path) -> Path:
    """Download the official MSI and extract administratively, without installation."""
    tool_dir = root / "tools" / f"espeak-ng-{ESPEAK_VERSION}"
    existing = list(tool_dir.rglob("espeak-ng.exe"))
    if existing:
        return existing[0]
    if os.name != "nt":
        raise RuntimeError("Use --espeak with an existing espeak-ng on Linux/macOS.")
    tool_dir.mkdir(parents=True, exist_ok=True)
    msi = tool_dir / "espeak-ng.msi"
    if not msi.is_file() or msi.stat().st_size != ESPEAK_BYTES:
        part = msi.with_suffix(".msi.part")
        with httpx.stream("GET", ESPEAK_URL, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with part.open("wb") as stream:
                for chunk in response.iter_bytes(1_048_576):
                    stream.write(chunk)
                    if stream.tell() > ESPEAK_BYTES:
                        raise RuntimeError("Unexpected MSI length.")
        if part.stat().st_size != ESPEAK_BYTES:
            raise RuntimeError("Incomplete MSI.")
        part.replace(msi)
    subprocess.run(
        ["msiexec", "/a", str(msi), "/qn", f"TARGETDIR={tool_dir / 'extracted'}"],
        check=True,
        timeout=300,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    existing = list(tool_dir.rglob("espeak-ng.exe"))
    if len(existing) != 1:
        raise RuntimeError("Cannot find the extracted espeak-ng executable.")
    return existing[0]


def prepare_fixtures(root: Path, executable: Path) -> Path:
    """Generate both fixtures from fixed text, before observing any ASR results."""
    version_output = subprocess.run(
        [str(executable), f"--path={executable.parent}", "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    match = re.search(r"text-to-speech:\s*(\S+)", version_output)
    if match is None or match[1] != ESPEAK_VERSION:
        raise ValueError(f"Expected eSpeak NG {ESPEAK_VERSION}; use the pinned preparation tool.")
    destination = root / "eval" / "VOICE-04" / "tts"
    destination.mkdir(parents=True, exist_ok=True)
    expected = PROMPTS[0]
    cases = [
        ("correct", expected, True),
        ("wrong", "tôi đang đọc một câu khác hoàn toàn với đề bài", False),
    ]
    rows = []
    for name, spoken, should_match in cases:
        text = destination / f"{name}.txt"
        audio = destination / f"{name}.wav"
        text.write_text(spoken, encoding="utf-8")
        subprocess.run(
            [
                str(executable),
                f"--path={executable.parent}",
                "-v",
                "vi",
                "-s",
                "150",
                "-f",
                str(text),
                "-w",
                str(audio),
            ],
            check=True,
            timeout=60,
        )
        rows.append(
            {
                "path": str(audio.resolve()),
                "expected": expected,
                "spoken": spoken,
                "should_match": should_match,
            }
        )
    manifest = destination / "manifest.json"
    manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    (destination / "SOURCE.md").write_text(
        f"# TTS fixtures VOICE-04\n\neSpeak NG {ESPEAK_VERSION}, voice vi, 150 words/minute.\n"
        f"Official tool: {ESPEAK_URL}\nExecutable SHA-256: {digest}\n"
        "GPL-3.0-or-later: standalone preparation tool only, no linked/copied production code.\n"
        "Terms: https://github.com/espeak-ng/espeak-ng/blob/1.52.0/COPYING (section 2).\n"
        "No online TTS service; network only downloads the preparation tool.\n"
        "Text authored in this repository; internal research fixtures, not redistributed.\n"
        "Do not infer a CC/public-domain license for generated audio.\n",
        encoding="utf-8",
    )
    return manifest


MMS_REVISION = "b58928d033932a49aa8e3d6cf11625b25fe928d2"
MMS_SHA256 = "55ded90c3e57dc2814fa2cdfe3f9e7a5c28e1223b06c0a260a4495b080762ffd"
MMS_FILES = {
    "config.json": 1641,
    "tokenizer_config.json": 289,
    "special_tokens_map.json": 49,
    "vocab.json": 1152,
    "model.safetensors": 145_271_288,
    "README.md": 3987,
}


def prepare_mms(root: Path, models_dir: Path, *, download: bool = False) -> Path:
    """Generate the same fixed texts using a pinned, local Vietnamese neural TTS."""
    directory = models_dir / "mms-tts-vie"
    if download:
        directory.mkdir(parents=True, exist_ok=True)
        for name, size in MMS_FILES.items():
            path = directory / name
            if path.is_file() and path.stat().st_size == size:
                continue
            part = path.with_suffix(path.suffix + ".part")
            url = f"https://huggingface.co/facebook/mms-tts-vie/resolve/{MMS_REVISION}/{name}"
            with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
                response.raise_for_status()
                with part.open("wb") as stream:
                    for chunk in response.iter_bytes(1_048_576):
                        stream.write(chunk)
                        if stream.tell() > size:
                            raise RuntimeError("TTS artifact exceeds pinned size.")
            if part.stat().st_size != size:
                raise RuntimeError("Incomplete TTS artifact.")
            part.replace(path)
            print(f"MMS preparation: {name}, {size} bytes", flush=True)
    if any(
        not (directory / name).is_file() or (directory / name).stat().st_size != size
        for name, size in MMS_FILES.items()
    ):
        raise RuntimeError("Prepare local MMS files first with --download-model.")
    if hashlib.sha256((directory / "model.safetensors").read_bytes()).hexdigest() != MMS_SHA256:
        raise RuntimeError("Pinned MMS weights SHA-256 mismatch.")
    import soundfile as sf
    import torch
    from transformers import AutoTokenizer, VitsModel, set_seed

    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(
        str(directory), local_files_only=True, trust_remote_code=False
    )
    model = (
        VitsModel.from_pretrained(
            str(directory),
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=True,
            dtype=torch.float32,
        )
        .to("cpu")
        .eval()
    )
    destination = root / "eval" / "VOICE04" / "tts-mms"
    destination.mkdir(parents=True, exist_ok=True)
    expected = PROMPTS[0]
    rows = []
    for name, spoken, should_match in (
        ("correct", expected, True),
        ("wrong", "tôi đang đọc một câu khác hoàn toàn với đề bài", False),
    ):
        set_seed(42)
        with torch.inference_mode():
            waveform = model(**tokenizer(spoken, return_tensors="pt")).waveform[0].numpy()
        audio = destination / f"{name}.wav"
        sf.write(audio, waveform, model.config.sampling_rate, subtype="PCM_16")
        rows.append(
            {
                "path": str(audio.resolve()),
                "expected": expected,
                "spoken": spoken,
                "should_match": should_match,
            }
        )
    manifest = destination / "manifest.json"
    manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    source = (
        f"# TTS preparation VOICE-04\n\nfacebook/mms-tts-vie@{MMS_REVISION}\n"
        f"Weights SHA-256: {MMS_SHA256}\nLicense: CC BY-NC 4.0, research/noncommercial.\n"
        f"https://huggingface.co/facebook/mms-tts-vie/blob/{MMS_REVISION}/README.md\n"
        "No online TTS service; explicit preparation download only; generation local CPU FP32.\n"
        "Same two fixed texts as the eSpeak experiment; seed 42 before each generation.\n"
        "Internal research audio, not redistributed. Do not claim a public-domain output license.\n"
    )
    (destination / "SOURCE.md").write_text(source, encoding="utf-8")
    (directory / "SOURCE.md").write_text(source, encoding="utf-8")
    return manifest


def main() -> None:
    """Prepare fixtures under DATA_DIR; model inference never invokes this script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("espeak", "mms"), default="mms")
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--espeak", type=Path)
    parser.add_argument("--download-tool", action="store_true")
    args = parser.parse_args()
    root = Path(os.getenv("DATA_DIR", "data")).resolve()
    if args.provider == "mms":
        models_dir = Path(os.getenv("MODELS_DIR", "models")).resolve()
        print(prepare_mms(root, models_dir, download=args.download_model))
        return
    executable = args.espeak or (prepare_tool(root) if args.download_tool else None)
    if executable is None:
        found = shutil.which("espeak-ng")
        if not found:
            parser.error("Use --espeak PATH or --download-tool (Windows).")
        executable = Path(found)
    print(prepare_fixtures(root, executable))


if __name__ == "__main__":
    main()
