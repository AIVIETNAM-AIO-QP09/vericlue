"""Closed server-owned ASR choices, independent of the six manual cutoff values."""

CONTENT_BACKENDS = ("qwen06", "qwen17")
QWEN17_SUBDIR = "qwen3-asr-17b-hf"


def validate_content_backend(backend: str, *, manual: bool) -> None:
    """The larger checkpoint is an explicit manual-full-demo selection only."""
    if backend not in CONTENT_BACKENDS or (backend == "qwen17" and not manual):
        raise ValueError("Unsupported voice content backend or mode")


def content_model_version(backend: str = "qwen06") -> str:
    """Return the complete immutable checkpoint/implementation identity, without loading."""
    if backend == "qwen06":
        from vericlue_ml.voice.qwen_asr import VERSION
    elif backend == "qwen17":
        from vericlue_ml.voice.qwen17_asr import VERSION
    else:
        raise ValueError("Unknown voice content backend")
    return VERSION


def content_pin_matches(pin: str | None, backend: str = "qwen06") -> bool:
    """Only legacy 0.6B sessions may lack a pin; never infer or backfill a 1.7B pin."""
    return pin == content_model_version(backend) or (pin is None and backend == "qwen06")
