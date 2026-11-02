"""Pinned Qwen 1.7B candidate for offline evaluation only; never an API backend.

Source: Qwen/Qwen3-ASR-1.7B-hf at
bcd2b5b7f32b480ab5790554cfa8347f246a14f3 (Apache-2.0 model card).
The seven file hashes were checked against that revision's Git blobs/LFS SHA256.
Uses installed Transformers 5.13.0 native code with local_files_only=True and
trust_remote_code=False, through the unchanged QwenASR implementation. Processor,
tokenizer, template and generation-config bytes match the pinned 0.6B checkpoint.
Only architecture configuration and weights differ; no prompt, VAD or budget fork.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from vericlue_ml.voice.qwen_asr import QwenASR

REVISION = "bcd2b5b7f32b480ab5790554cfa8347f246a14f3"
VERSION = f"qwen3-asr-17b@{REVISION}+cpu-fp32-content-v2-assistant-prefix"
PINNED_CONFIG = MappingProxyType(
    {
        "repo": "Qwen/Qwen3-ASR-1.7B-hf",
        "revision": REVISION,
        "model_subdir": ".",
        "cpu_threads": 4,
        "sha256": MappingProxyType(
            {
                "chat_template.jinja": "f50e6b694fbf4a683206e37869990d68333fe95d285730f084c838a34b0d98c2",
                "config.json": "117ac8e63e2af7cae3665e5a632d6eb03f5f384915519ceb6403c15ec6533f63",
                "generation_config.json": "9939fc9388b79bd70757f938b87381e817173d6a6158f5af6506c0b73e775c3c",
                "model.safetensors": "2db53c7d81bd9b8cbc6a074e89be2c968a0d373fb4ee68bb1b1e14f7042dfee1",
                "processor_config.json": "bc0b230081b44e629dd5b9045b78495615c1831b4b9f4cffe97bd37e82a6156a",
                "tokenizer.json": "fe1fad59be22a41ee293363fcf95fdedbc7c93f3b49270b1d2e18bd1399a7a05",
                "tokenizer_config.json": "945e980986de2ca7768f3326bfdbb4fbea3406f972b8ae0be233089f2b253c11",
            }
        ),
    }
)


class Qwen17ASR(QwenASR):
    """Offline candidate root; production configuration overrides cannot change its pins."""

    version = VERSION
    _revision = REVISION

    def _read_config(self, _repo: Path) -> Mapping[str, Any]:
        return PINNED_CONFIG
