"""Sign the verified CI build locally. The private APK key never leaves this laptop."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    "VeriClue-unsigned.apk",
    "apksigner.jar",
    "ANDROID-BUILD-TOOLS-NOTICE.txt",
    "build-info.json",
}


def check_build(folder: Path, expected_source: str) -> dict:
    """Reject incomplete, changed or wrong-revision inputs before using the signing key."""
    if not re.fullmatch(r"[a-f0-9]{40}", expected_source):
        raise ValueError("Cần commit nguồn đầy đủ đã kiểm tra.")
    listed = {}
    for line in (folder / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        if name not in INPUTS or name in listed or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Danh sách checksum không hợp lệ.")
        path = folder / name
        if path.is_symlink() or path.resolve().parent != folder.resolve():
            raise ValueError("Đường dẫn artifact không hợp lệ.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Artifact đã thay đổi; không ký.")
        listed[name] = digest
    if listed.keys() != INPUTS:
        raise ValueError("Thiếu thành phần build.")
    info = json.loads((folder / "build-info.json").read_text(encoding="utf-8"))
    if (
        info.get("source_head_sha") != expected_source
        or info.get("application_id") != "vn.vericlue.app"
        or info.get("signing") != "required_on_laptop"
        or info.get("signed_media") is not True
    ):
        raise ValueError("Build không đúng commit/package/cấu hình cần ký.")
    return info


def run_tool(java: Path, jar: Path, args: list[str]) -> str:
    result = subprocess.run(
        [str(java), "-jar", str(jar), *args],
        capture_output=True,
        encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        # Do not print signing-tool diagnostics, keystore details or password material.
        raise ValueError("Công cụ ký/kiểm chứng APK báo lỗi.")
    return result.stdout


def require_pinned_signature(report: str, pin: str) -> None:
    """Handle SDK output for v2/v3 signers; require only the pinned certificate."""
    certs = re.findall(r"certificate SHA-256 digest: ([a-f0-9]{64})", report)
    modern = re.search(r"Verified using v[23](?:\.\d+)? scheme[^\n]*: true", report)
    if set(certs) != {pin} or not modern:
        raise ValueError("Chữ ký APK không đúng khóa đã chốt hoặc thiếu v2/v3.")


def sign_build(folder: Path, expected_source: str, java: Path, store: Path, output: Path) -> Path:
    info = check_build(folder, expected_source)
    key = store / "vericlue-demo.p12"
    password = store / "password.txt"
    if not all(path.is_file() for path in (java, key, password)):
        raise ValueError("Thiếu Java hoặc khóa ký hiện có; không tạo khóa thay thế.")
    pin = (ROOT / "apps/android/demo-signing-cert.sha256").read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[a-f0-9]{64}", pin):
        raise ValueError("Pin chữ ký không hợp lệ.")
    jar = folder / "apksigner.jar"
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="sign-", dir=output) as temporary:
        apk = Path(temporary) / "VeriClue.apk"
        run_tool(
            java,
            jar,
            [
                "sign",
                "--ks",
                str(key),
                "--ks-type",
                "PKCS12",
                "--ks-key-alias",
                "vericlue-demo",
                "--ks-pass",
                "file:" + str(password),
                "--v2-signing-enabled",
                "true",
                "--out",
                str(apk),
                str(folder / "VeriClue-unsigned.apk"),
            ],
        )
        verified = run_tool(java, jar, ["verify", "--verbose", "--print-certs", str(apk)])
        require_pinned_signature(verified, pin)
        digest = hashlib.sha256(apk.read_bytes()).hexdigest()
        info.update({"signing": "signed_on_laptop", "signer_sha256": pin, "apk_sha256": digest})
        (Path(temporary) / "build-info.json").write_text(
            json.dumps(info, indent=2) + "\n", encoding="utf-8"
        )
        (Path(temporary) / "SHA256SUMS.txt").write_text(
            digest + "  VeriClue.apk\n", encoding="ascii"
        )
        for name in ("VeriClue.apk", "build-info.json", "SHA256SUMS.txt"):
            os.replace(Path(temporary) / name, output / name)
    return output / "VeriClue.apk"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--java", required=True, type=Path)
    parser.add_argument("--store-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        apk = sign_build(
            args.build_dir.resolve(),
            args.expected_source,
            args.java.resolve(),
            args.store_dir.resolve(),
            args.output_dir.resolve(),
        )
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from None
    print(json.dumps({"apk": str(apk), "signature_verified": True, "key_uploaded": False}))


if __name__ == "__main__":
    main()
