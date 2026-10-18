"""Optional checkpoint smoke: synthetic tensors only, no audio/video dataset access."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


@pytest.mark.slow
def test_real_syncnet_checkpoint_produces_finite_unit_embeddings() -> None:
    """Verify strict local loading and both encoder shapes without claiming accuracy."""
    configured = os.getenv("MODELS_DIR")
    if not configured:
        pytest.skip("Set MODELS_DIR to opt into the local SyncNet checkpoint smoke")
    root = Path(configured).expanduser()
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    if not (root / "syncnet" / "stable_syncnet.pt").is_file():
        pytest.skip("Local stable_syncnet.pt checkpoint is unavailable")
    if importlib.util.find_spec("torch") is None:
        pytest.skip("Checkpoint smoke requires the optional torch dependency")

    # All opt-in checks precede Torch import or checkpoint loading.
    import numpy as np

    from vericlue_ml.voice.syncnet import StableBackend

    backend = StableBackend()
    try:
        backend.preload(models_dir=root, device="cpu")
        assert backend.model is not None
        crops = [np.full((256, 256, 3), 128, dtype=np.uint8) for _ in range(16)]
        mel = np.zeros((80, 52), dtype=np.float32)
        video_embedding = backend.embed_video(crops)
        audio_embedding = backend.embed_audio(mel)
        for embedding in (video_embedding, audio_embedding):
            assert embedding.shape == (2048,)
            assert np.isfinite(embedding).all()
            assert np.linalg.norm(embedding) == pytest.approx(1.0, abs=1e-6)
    finally:
        backend.model = None
