"""Compatibility facade; all eKYC decisions now delegate to the ML TrustRouter."""

from vericlue_ml.router.config import load_config
from vericlue_ml.router.fusion import FusionError, max_probability
from vericlue_ml.router.policy import (
    FACE_MODULES,
    FINALIZE_MODULES,
    MAX_VOICE_REREADS,
    PRESENCE_MODULES,
    VOICE_MODULES,
    VOICE_STEP_MODULES,
    TrustRouter,
)
from vericlue_ml.router.policy import (
    Decision as Outcome,
)

__all__ = [
    "FACE_MODULES",
    "FINALIZE_MODULES",
    "MAX_VOICE_REREADS",
    "PRESENCE_MODULES",
    "VOICE_MODULES",
    "VOICE_STEP_MODULES",
    "Outcome",
    "decide_finalize",
    "decide_voice",
    "fused_prob",
]


def fused_prob(results, modules):
    """Compatibility for staff/forensic reads; never ignore a missing required result."""
    try:
        return max_probability(results, modules)
    except FusionError:
        return None


def decide_finalize(results, *, retries_used, max_retries, b, a):
    """Legacy call signature; callers cannot override the locked YAML values."""
    config = load_config()
    if (b, a) != (config.face.b, config.face.a):
        raise ValueError("Threshold overrides must use thresholds.yaml")
    return TrustRouter(config).finalize(results, retries_used=retries_used, max_retries=max_retries)


def decide_voice(results, *, rereads_used, b):
    """Legacy signature: B is checked for compatibility, never used as the voice threshold."""
    config = load_config()
    if b != config.face.b:
        raise ValueError("Threshold overrides must use thresholds.yaml")
    return TrustRouter(config).voice(results, rereads_used=rereads_used)
