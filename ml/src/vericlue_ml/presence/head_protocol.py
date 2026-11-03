"""Server capture identities; adaptive measurement is distinct from nominal wire timing."""

from collections.abc import Mapping

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode
from vericlue_ml.presence.challenge import expected_dynamic
from vericlue_ml.presence.landmarks import LandmarkError


def head_protocol_version(inp: DetectorInput) -> int:
    """Validate the bound plan and return its measurement protocol (adaptive is 3)."""
    return head_capture_protocol(expected_dynamic(inp))


def head_capture_protocol(dynamic: Mapping) -> int:
    """Keep wire v1/v2 compatible while assigning adaptive sampling its own identity."""
    version = dynamic.get("version")
    start, duration = dynamic.get("head_start_at_ms"), dynamic.get("head_duration_ms")
    mode, timeout = dynamic.get("head_mode"), dynamic.get("head_timeout_ms")
    if (
        type(version) is not int
        or version not in (1, 2)
        or type(start) is not int
        or type(duration) is not int
        or duration != {1: 6000, 2: 12000}.get(version)
        or start < 500
        or start + duration > 30000
        or mode not in (None, "adaptive")
        or (mode is None and timeout is not None)
        or (
            mode == "adaptive"
            and (type(timeout) is not int or not 6000 <= timeout <= 30000 - start)
        )
    ):
        raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
    return 3 if mode == "adaptive" else version


def head_identity_suffix(protocol: int) -> str:
    """Bind identity/consistency artifacts to the actual head sampling protocol."""
    if type(protocol) is not int or protocol not in (1, 2, 3):
        raise ValueError("Unknown head protocol")
    return {1: "", 2: "+head12s-v2", 3: "+head-adaptive-v1"}[protocol]


def session_model_version(base: str, protocol: int) -> str:
    """Keep calibration identity specific to the capture protocol."""
    if type(protocol) is not int or protocol not in (1, 2, 3):
        raise ValueError("Unknown head protocol")
    return base + ("+session-video-v3-adaptive" if protocol == 3 else f"+session-video-v{protocol}")
