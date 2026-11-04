"""No real weights: backend selection, integrity, reuse and conflict guards."""

import hashlib
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.services import wechat_qr
from vericlue_api.services.card_scanner import CardScanner
from vericlue_api.services.identity_runtime import IdentityRuntime

QR = "001099012345||Test Person|01011995|Nam|Test Address|15062021"


def fake_weights(tmp_path, monkeypatch):
    folder = tmp_path / wechat_qr.MODEL_SUBDIR
    folder.mkdir()
    pins = {}
    for name in wechat_qr.MODEL_SHA256:
        data = name.encode()
        (folder / name).write_bytes(data)
        pins[name] = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(wechat_qr, "MODEL_SHA256", pins)
    return folder


def test_verified_weights_load_once_and_reuse_native_detector(tmp_path, monkeypatch):
    fake_weights(tmp_path, monkeypatch)
    loads = []

    def create(*paths):
        loads.append(paths)
        return SimpleNamespace(detectAndDecode=lambda _: ([QR, ""], []))

    monkeypatch.setattr(cv2, "wechat_qrcode_WeChatQRCode", create, raising=False)
    decoder = wechat_qr.WeChatQR(tmp_path)
    decoder.preload()
    for _ in range(2):
        assert decoder.decode(np.zeros((100, 100, 3), np.uint8)) == {QR}
    assert len(loads) == 1 and len(loads[0]) == 4


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_modified_weights_reject_before_native_load(tmp_path, monkeypatch, missing):
    folder = fake_weights(tmp_path, monkeypatch)
    if missing:
        (folder / "detect.caffemodel").unlink()
    else:
        (folder / "detect.caffemodel").write_bytes(b"changed")

    def forbidden(*_):
        pytest.fail("Unverified model must not enter OpenCV")

    monkeypatch.setattr(cv2, "wechat_qrcode_WeChatQRCode", forbidden, raising=False)
    with pytest.raises(ValueError, match="WeChat QR"):
        wechat_qr.WeChatQR(tmp_path).preload()


def test_wechat_and_zxing_conflict_is_preserved_without_legacy_fallback(tmp_path, monkeypatch):
    other = QR.replace("001099012345", "001099999999")
    scanner = CardScanner(portrait_check=lambda _: True, models_dir=tmp_path, qr_backend="wechat")
    monkeypatch.setattr(scanner._wechat, "decode", lambda _: {other})

    def forbidden():
        pytest.fail("Selected WeChat backend must not invoke legacy QRCodeDetector")

    monkeypatch.setattr(cv2, "QRCodeDetector", forbidden)
    zxing = SimpleNamespace(
        BarcodeFormat=SimpleNamespace(QRCode=1),
        read_barcodes=lambda *a, **k: [SimpleNamespace(valid=True, text=QR)],
    )
    assert scanner._decode_qr(np.zeros((120, 200, 3), np.uint8), zxing) == {QR, other}


def test_wechat_failure_does_not_accept_zxing_only(tmp_path, monkeypatch):
    scanner = CardScanner(models_dir=tmp_path, qr_backend="wechat")

    def broken(_):
        raise RuntimeError("backend failed")

    monkeypatch.setattr(scanner._wechat, "decode", broken)
    zxing = SimpleNamespace(
        BarcodeFormat=SimpleNamespace(QRCode=1),
        read_barcodes=lambda *a, **k: [SimpleNamespace(valid=True, text=QR)],
    )
    with pytest.raises(RuntimeError, match="backend failed"):
        scanner._decode_qr(np.zeros((120, 200, 3), np.uint8), zxing)


def test_runtime_selects_wechat_and_missing_weights_are_unavailable(tmp_path):
    runtime = IdentityRuntime(Settings(identity_qr_backend="wechat", models_dir=str(tmp_path)))
    assert runtime._create_scanner()._wechat is not None
    with pytest.raises(ApiError) as error:
        runtime.preload()
    assert error.value.status_code == 503
    assert runtime._scanner is None
