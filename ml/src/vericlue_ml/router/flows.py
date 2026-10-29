"""FLOW-01: purpose-specific policy over existing detector decisions, without I/O."""

from dataclasses import replace
from typing import Literal

from vericlue_ml.router.policy import Decision

SessionPurpose = Literal["onboarding", "reauth", "recovery"]


def route_face(
    decision: Decision, purpose: SessionPurpose | None, *, device_verified: bool = False
) -> Decision:
    """Never upgrade a failed gate to pass; device trust is supplied only by the server."""
    if purpose is None:
        return decision
    if purpose == "reauth":
        if not device_verified:
            return replace(decision, status="recovery_required", reason="device not verified")
        if decision.status in {"review", "retry"}:
            return replace(decision, status="deny")
        return decision
    if purpose not in {"onboarding", "recovery"}:
        raise ValueError("Unknown session purpose")
    # Onboarding reads a sentence only when the face is unclear (B < face < A, from the router);
    # recovery, the account-takeover path, always reads. Voice cannot clear review: the API keeps it.
    if purpose == "recovery" and decision.status == "pass":
        return replace(decision, status="voice_challenge", reason="voice required by purpose")
    return decision


def route_voice(decision: Decision, purpose: SessionPurpose | None) -> Decision:
    """Reauthentication never creates a staff review case."""
    if purpose not in {None, "onboarding", "reauth", "recovery"}:
        raise ValueError("Unknown session purpose")
    if purpose == "reauth" and decision.status == "review":
        return replace(decision, status="deny")
    return decision
