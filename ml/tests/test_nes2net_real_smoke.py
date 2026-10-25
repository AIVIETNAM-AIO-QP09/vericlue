"""Opt-in real CPU checkpoint and upstream head parity; synthetic signals only."""

import ast
import hashlib
import os
from pathlib import Path

import numpy as np
import pytest


@pytest.mark.slow
def test_nes2net_checkpoint_cpu_and_repeatability():
    root = os.getenv("NES2NET_MODELS_DIR")
    if not root:
        pytest.skip("Set NES2NET_MODELS_DIR in the separate NES2Net runtime")
    import torch

    from vericlue_ml.voice.nes2net import Nes2NetBackend, Nes2NetDetector

    backend = Nes2NetBackend(Path(root))
    backend.preload()
    loaded = backend._model
    backend.preload()
    assert backend._model is loaded
    assert next(loaded.parameters()).device.type == "cpu"
    assert next(loaded.parameters()).dtype == torch.float32 and not loaded.training
    assert backend.load_report["missing_keys"] == []
    assert backend.load_report["unexpected_keys"] == []
    signal = np.random.default_rng(42).normal(0, 0.02, 64000).astype(np.float32)
    first, second = backend.logits(signal), backend.logits(signal)
    assert first.shape == (2,) and np.isfinite(first).all()
    np.testing.assert_allclose(first, second, rtol=0, atol=0)
    assert backend.load_report["head_keys"] > 0
    detector = Nes2NetDetector(backend=backend)
    result = detector.predict_samples(np.zeros(64000, np.float32))
    assert result.status == "not_applicable" and result.prob_attack is None


@pytest.mark.slow
def test_head_graph_matches_pinned_original_on_synthetic_features():
    source_path = os.getenv("NES2NET_UPSTREAM_SOURCE")
    if not source_path:
        pytest.skip("Set NES2NET_UPSTREAM_SOURCE to the verified pinned upstream file")
    import math

    import torch

    from vericlue_ml.voice._nes2net_arch import Nested_Res2Net_TDNN

    source = Path(source_path).read_bytes()
    assert (
        hashlib.sha256(source).hexdigest()
        == "8a81756688e026243b40c0a8733e2d122401322c74cb32add8046f9bb60bc75f"
    )
    # Execute only audited licensed head classes, not Fairseq loader or upstream main.
    tree = ast.parse(source.decode("utf-8"))
    names = {"SEModule", "Bottle2neck", "ASTP", "Nested_Res2Net_TDNN"}
    module = ast.Module(
        body=[node for node in tree.body if isinstance(node, ast.ClassDef) and node.name in names],
        type_ignores=[],
    )
    scope = {"torch": torch, "nn": torch.nn, "math": math}
    exec(compile(module, "verified-upstream-head", "exec"), scope)
    torch.manual_seed(42)
    port = Nested_Res2Net_TDNN(Nes_ratio=(8, 8), SE_ratio=(1,)).eval()
    upstream = scope["Nested_Res2Net_TDNN"](Nes_ratio=[8, 8], SE_ratio=[1]).eval()
    upstream.load_state_dict(port.state_dict(), strict=True)
    with torch.inference_mode():
        for frames in (49, 199):
            features = torch.randn(1, 1024, frames)
            torch.testing.assert_close(port(features), upstream(features), rtol=0, atol=0)
