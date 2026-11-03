"""Exercise the local synthetic Android demo through consent, OTP and real card decoding.

Never uses a person's session, phone, card or face. Withdraws its own diagnostic
session afterward. Run with the existing server runtime Python and --run-synthetic.
"""

from __future__ import annotations

import argparse
import base64
import re
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8421"


def check_profile(values: dict[str, str | None]) -> None:
    """Reject incompatible local configuration before making any HTTP requests."""
    required = {
        "SECURITY_PROFILE": "synthetic",
        "SIMULATED_OTP": "true",
        "PRIVACY_POLICY_VERSION": "demo-v1",
        "IDENTITY_CARD_ENABLED": "true",
    }
    for name, expected in required.items():
        if (values.get(name) or "").lower() != expected:
            raise ValueError(f"Local Android demo requires {name}={expected}")


def run() -> None:
    """Probe the running loopback API using only generated synthetic data."""
    import cv2
    import httpx
    import numpy as np
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    spki = base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode()
    with httpx.Client(base_url=BASE, timeout=60, trust_env=False) as client:

        def request(method: str, path: str, **kwargs) -> dict:
            response = client.request(method, path, **kwargs)
            data = response.json()
            if response.is_error:
                # Never log token, response body, session URL, phone, OTP or document fields.
                code = data.get("error_code", "unknown")
                if not isinstance(code, str) or not re.fullmatch(r"[a-z_]{1,80}", code):
                    code = "unknown"
                raise RuntimeError(f"HTTP {response.status_code}: {code}")
            return data

        assert request("GET", "/healthz")["status"] == "ok"
        session = request(
            "POST",
            "/v1/sessions",
            json={
                "purpose": "onboarding",
                "head_mode": "adaptive",
                "nonce": "diagnostic_" + secrets.token_urlsafe(20),
                "device_public_key_spki": spki,
            },
        )
        assert session["challenge"].get("media_nonce")
        path = "/v1/sessions/" + session["session_id"]
        client.headers["Authorization"] = "Bearer " + session["token"]
        try:
            privacy = request("GET", path + "/privacy")
            assert privacy["policy_version"] == "demo-v1"
            granted = request(
                "POST",
                path + "/privacy/consent",
                json={
                    "policy_version": "demo-v1",
                    "consent": True,
                    "categories": ["contact", "id_document", "face_biometrics", "voice_biometrics"],
                },
            )
            assert granted["status"] == "granted" and granted["consent_receipt_id"]
            template = request("GET", path + "/privacy/account-template")
            assert template["policy_version"] == "account-template-v1"
            assert template["retention_seconds"] == 86400
            granted = request(
                "POST",
                path + "/privacy/account-template/consent",
                json={
                    "policy_version": "account-template-v1",
                    "purpose": "account_template",
                    "consent": True,
                },
            )
            assert granted["status"] == "granted" and granted["consent_receipt_id"]
            print("PASS: processing and account-template consent on synthetic session")
            otp = request("POST", path + "/otp", json={"phone": "0900000000"})
            code = re.search(r"\b[0-9]{6}\b", otp["simulated_sms"]).group()
            wrong = "000001" if code == "000000" else "000000"
            assert request("POST", path + "/otp/verify", json={"code": wrong})["status"] == "retry"
            assert request("POST", path + "/otp/verify", json={"code": code})["status"] == "pass"
            print("PASS: simulated OTP issued; incorrect rejected; correct accepted")
            qr = cv2.QRCodeEncoder_create().encode(
                "001099012345||Synthetic Diagnostic|01011995|Nam|Synthetic Address|15062021"
            )
            qr = cv2.copyMakeBorder(qr, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
            qr = cv2.resize(qr, (320, 320), interpolation=cv2.INTER_NEAREST)
            card = np.full((560, 900, 3), 235, np.uint8)
            card[100:420, 500:820] = cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR)
            ok, image = cv2.imencode(".png", card)
            assert ok
            result = request(
                "POST",
                path + "/id-card",
                files={
                    "front": ("synthetic-card.png", image.tobytes(), "image/png"),
                },
            )
            assert result["status"] == "retry" and result["retry_hint"] == "PORTRAIT_UNREADABLE"
            assert not result.get("fields")
            print("PASS: real QR decoder read generated card; missing portrait correctly rejected")
        finally:
            result = request("POST", path + "/privacy/withdraw", json={"confirm": True})
            assert result["status"] == "withdrawn"
            print("PASS: diagnostic session withdrawn; no real user consent modified")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / "tmp/vericlue-server")
    parser.add_argument("--run-synthetic", action="store_true", required=True)
    args = parser.parse_args()
    from dotenv import dotenv_values

    check_profile(dotenv_values(args.runtime_dir / ".env"))
    run()


if __name__ == "__main__":
    main()
