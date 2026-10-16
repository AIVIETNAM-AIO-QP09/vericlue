"""Shared module groups and staff/forensic fusion helper; no decision-policy wrappers."""

from vericlue_ml.router.fusion import FusionError, max_probability
from vericlue_ml.router.policy import (
    FACE_MODULES,
    FINALIZE_MODULES,
    MAX_VOICE_REREADS,
    PRESENCE_MODULES,
    VOICE_MODULES,
    VOICE_STEP_MODULES,
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
    "fused_prob",
]


def fused_prob(results, modules):
    """Compatibility for staff/forensic reads; never ignore a missing required result."""
    try:
        return max_probability(results, modules)
    except FusionError:
        return None
