"""Resolve a server-owned dynamic challenge bound to this session and attempt."""

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode
from vericlue_ml.presence.landmarks import LandmarkError


def expected_dynamic(inp: DetectorInput) -> dict:
    challenge = inp.metadata.get("expected_challenge")
    dynamic = challenge.get("dynamic") if isinstance(challenge, dict) else None
    if (
        not isinstance(dynamic, dict)
        or not inp.session_id
        or dynamic.get("session_id") != inp.session_id
        or not inp.metadata.get("challenge_id")
        or inp.metadata["challenge_id"] != challenge.get("challenge_id")
        or type(dynamic.get("version")) is not int
        or dynamic["version"] != 1
    ):
        raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
    return dynamic
