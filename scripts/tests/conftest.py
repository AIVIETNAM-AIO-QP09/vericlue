"""Keep synthetic download tests independent of the host disk's free space."""

from __future__ import annotations

import shutil

import pytest

_SYNTHETIC_DOWNLOAD_MODULES = frozenset(
    {
        "test_download_data.py",
        "test_mlaad_metadata.py",
        "test_zalo_whole.py",
        "test_zip_adversarial.py",
    }
)


@pytest.fixture(autouse=True)
def synthetic_download_disk(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Model a roomy disk for tiny offline fixtures; tests may override it to assert low-space guards."""
    if request.path.name not in _SYNTHETIC_DOWNLOAD_MODULES:
        return
    core = request.module.core
    # Do not bypass check_disk: explicit low-space tests replace this after fixture setup.
    monkeypatch.setattr(
        core.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(100_000_000_000, 1_000_000_000, 99_000_000_000),
    )
