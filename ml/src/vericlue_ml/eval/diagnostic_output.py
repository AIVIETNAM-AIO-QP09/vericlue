"""Validate destinations for research reports, never deployment artifacts."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def check_diagnostic_output(
    output: Path, *, protected: Iterable[Path], models_dir: Path | None = None
) -> Path:
    """Require a new file outside input and configured runtime storage.

    Call again immediately before writing: configuration and symlink targets may
    change during measurement. Fitted calibrator writers intentionally use their
    own explicit destination policy rather than this diagnostic-only guard.
    """
    target = output.resolve()
    if target.exists() or target in {path.resolve() for path in protected}:
        raise ValueError("Output must be new and outside input storage")
    forbidden = [
        ROOT / name
        for name in ("ml/configs", "configs", "models", "data", "external", "packages/contracts")
    ]
    forbidden.extend(
        Path(os.environ[key])
        for key in ("MODELS_DIR", "DATA_DIR", "CALIBRATORS_DIR")
        if os.environ.get(key)
    )
    if models_dir is not None:
        forbidden.append(models_dir)
    if any(target.is_relative_to(path.resolve()) for path in forbidden):
        raise ValueError("Diagnostic output must be outside config/model/data/calibrator storage")
    return target
