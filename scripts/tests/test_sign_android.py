"""Reject changed or wrong-source artifacts before opening the APK signing key."""

import hashlib
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

_spec = spec_from_file_location(
    "vericlue_sign_android", Path(__file__).parents[1] / "sign_android.py"
)
signer = module_from_spec(_spec)
_spec.loader.exec_module(signer)
SHA = "a" * 40


@pytest.fixture
def build(tmp_path):
    info = {
        "source_head_sha": SHA,
        "application_id": "vn.vericlue.app",
        "signing": "required_on_laptop",
        "signed_media": True,
    }
    for name in signer.INPUTS:
        (tmp_path / name).write_bytes(
            json.dumps(info).encode() if name == "build-info.json" else b"synthetic"
        )
    (tmp_path / "SHA256SUMS.txt").write_text(
        "".join(
            hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() + "  " + name + "\n"
            for name in sorted(signer.INPUTS)
        )
    )
    return tmp_path


def test_changed_binary_is_rejected(build):
    (build / "VeriClue-unsigned.apk").write_bytes(b"changed")
    with pytest.raises(ValueError, match="thay đổi"):
        signer.check_build(build, SHA)


def test_other_source_is_rejected(build):
    with pytest.raises(ValueError, match="commit/package"):
        signer.check_build(build, "b" * 40)


def test_checksum_path_traversal_is_rejected(build):
    with (build / "SHA256SUMS.txt").open("a") as out:
        out.write("0" * 64 + "  ../private-key.p12\n")
    with pytest.raises(ValueError, match="checksum"):
        signer.check_build(build, SHA)


@pytest.mark.parametrize(("scheme", "prefix"), [("v2", "Signer #1"), ("v3", "V3.0 Signer:")])
def test_sdk_signer_output_formats(scheme, prefix):
    pin = "a" * 64
    signer.require_pinned_signature(
        f"Verified using {scheme} scheme (APK Signature Scheme): true\n"
        f"{prefix} certificate SHA-256 digest: {pin}\n",
        pin,
    )


def test_different_certificate_cannot_pass():
    with pytest.raises(ValueError, match="Chữ ký"):
        signer.require_pinned_signature(
            "Verified using v3 scheme: true\nV3.0 Signer: certificate SHA-256 digest: " + "b" * 64,
            "a" * 64,
        )


def test_certificate_alone_without_verified_modern_signature_cannot_pass():
    with pytest.raises(ValueError, match="Chữ ký"):
        signer.require_pinned_signature(
            "Signer #1 certificate SHA-256 digest: " + "a" * 64, "a" * 64
        )
