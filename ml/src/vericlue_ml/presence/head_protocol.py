"""Exact server-owned head timing protocols shared by runtime and measurement tools."""

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode
from vericlue_ml.presence.challenge import expected_dynamic
from vericlue_ml.presence.landmarks import LandmarkError


def head_protocol_version(inp: DetectorInput) -> int:
    """Validate the version/duration pair and bounded video end before any decoding."""
    dynamic = expected_dynamic(inp)
    version = dynamic["version"]
    start, duration = dynamic.get("head_start_at_ms"), dynamic.get("head_duration_ms")
    if (
        type(start) is not int
        or type(duration) is not int
        or duration != {1: 6000, 2: 12000}[version]
        or start < 500
        or start + duration > 30000
    ):
        raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
    return version


def head_sampling_suffix(protocol: int, *, adaptive: bool = False) -> str:
    """Separate timed and adaptive selected-view artifact identities."""
    if type(protocol) is not int or protocol not in (1, 2):
        raise ValueError("Unknown head protocol")
    return ("+head12s-v2" if protocol == 2 else "") + ("+head-adaptive-v1" if adaptive else "")


def session_model_version(base: str, protocol: int, *, adaptive: bool = False) -> str:
    """Keep calibration identity specific to the capture protocol."""
    if type(protocol) is not int or protocol not in (1, 2):
        raise ValueError("Unknown head protocol")
    return base + f"+session-video-v{protocol}" + ("+head-adaptive-v1" if adaptive else "")
