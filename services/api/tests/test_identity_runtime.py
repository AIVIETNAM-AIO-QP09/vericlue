"""The card reader is owned by one API instance and never calls another HTTP server."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.services.identity_runtime import IdentityRuntime


def test_concurrent_scans_share_one_preloaded_reader(monkeypatch):
    runtime = IdentityRuntime(Settings(_env_file=None))
    loads = []
    creates = []
    scanner = SimpleNamespace(
        preload=lambda: loads.append(True),
        scan=lambda front, back: {"qr_values": [], "portrait_usable": False},
    )

    def create():
        creates.append(True)
        return scanner

    monkeypatch.setattr(runtime, "_create_scanner", create)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: runtime.scan(b"front", None), range(8)))
    assert len(creates) == len(loads) == 1
    assert all(result == {"qr_values": [], "portrait_usable": False} for result in results)


def test_missing_scanner_never_falls_back_or_exposes_details(monkeypatch):
    runtime = IdentityRuntime(Settings(_env_file=None))

    def broken():
        raise RuntimeError("private-file-or-card-content")

    monkeypatch.setattr(runtime, "_create_scanner", broken)
    with pytest.raises(ApiError) as exc:
        runtime.scan(b"front", None)
    assert exc.value.status_code == 503
    assert "private-file" not in str(exc.value)
    assert runtime._scanner is None
