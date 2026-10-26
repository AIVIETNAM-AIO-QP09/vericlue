"""Actual Ed25519 operations and hostile envelopes; no model weights or biometric accuracy."""

import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from vericlue_api.core.signing import (
    DOMAIN,
    ResultSigner,
    decode,
    encode,
    load_private_key,
    load_public_key,
    public_key_fingerprint,
    sign,
    verify,
    verify_result,
)
from vericlue_api.schemas.result import ResultClaims


def claims(**changes):
    return ResultClaims(
        **dict(
            {
                "version": 1,
                "issuer": "https://vericlue.example",
                "audience": "demo-integrator",
                "result_id": "res_" + "a" * 64,
                "session_id": "ses_synthetic",
                "purpose": "reauth",
                "nonce": "synthetic_nonce_123456",
                "status": "pass",
                "issued_at": 1800000000,
                "expires_at": 1800000060,
                "account_id": "acct_" + "b" * 32,
                "device_id": "dev_" + "c" * 32,
            },
            **changes,
        )
    )


def context(**changes):
    return dict(
        {
            "issuer": "https://vericlue.example",
            "audience": "demo-integrator",
            "session_id": "ses_synthetic",
            "nonce": "synthetic_nonce_123456",
            "purpose": "reauth",
            "now": 1800000001,
        },
        **changes,
    )


def test_actual_sign_verify_and_public_fingerprint():
    private = Ed25519PrivateKey.generate()
    message = b"synthetic bytes"
    signature = sign(message, private)
    assert len(signature) == 64 and verify(message, signature, private.public_key())
    assert not verify(message + b"!", signature, private.public_key())
    assert not verify(message, signature, Ed25519PrivateKey.generate().public_key())
    signer = ResultSigner(private)
    envelope = signer.issue(claims())
    assert signer.issue(claims()) == envelope
    assert public_key_fingerprint(private.public_key()) == envelope.key_id
    assert verify_result(envelope, private.public_key(), **context()) == claims()
    assert base64.b64decode(
        signer.public_key().public_key_spki
    ) == private.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )


@pytest.mark.parametrize(
    "fault",
    [
        "payload",
        "signature",
        "key_id",
        "wrong_key",
        "issuer",
        "audience",
        "session",
        "nonce",
        "purpose",
        "expired",
        "future",
        "padded",
        "bool_now",
        "algorithm",
    ],
)
def test_tamper_wrong_context_and_expiry_rejected(fault):
    key = Ed25519PrivateKey.generate()
    envelope = ResultSigner(key).issue(claims())
    trusted = key.public_key()
    expected = context()
    if fault == "payload":
        envelope = envelope.model_copy(
            update={"payload": encode(decode(envelope.payload).replace(b"pass", b"deny"))}
        )
    elif fault == "signature":
        raw = bytearray(decode(envelope.signature))
        raw[-1] ^= 1
        envelope = envelope.model_copy(update={"signature": encode(bytes(raw))})
    elif fault == "key_id":
        envelope = envelope.model_copy(update={"key_id": "d" * 64})
    elif fault == "wrong_key":
        trusted = Ed25519PrivateKey.generate().public_key()
    elif fault == "issuer":
        expected["issuer"] = "different-issuer"
    elif fault == "audience":
        expected["audience"] = "different-integrator"
    elif fault == "session":
        expected["session_id"] = "ses_other"
    elif fault == "nonce":
        expected["nonce"] = "different_nonce_12345"
    elif fault == "purpose":
        expected["purpose"] = "recovery"
    elif fault == "expired":
        expected["now"] = 1800000060
    elif fault == "future":
        expected["now"] = 1799999999
    elif fault == "padded":
        envelope = envelope.model_copy(update={"payload": envelope.payload + "="})
    elif fault == "bool_now":
        expected["now"] = True
    elif fault == "algorithm":
        envelope = envelope.model_copy(update={"algorithm": "none"})
    with pytest.raises(ValueError, match="Result not accepted"):
        verify_result(envelope, trusted, **expected)


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "extra",
        "no_version",
        "bool_version",
        "float_time",
        "long_ttl",
        "null_account",
        "missing_device",
        "recovery_deny",
    ],
)
def test_even_signed_malformed_claims_cannot_be_accepted(fault):
    key = Ed25519PrivateKey.generate()
    signer = ResultSigner(key)
    envelope = signer.issue(claims())
    value = claims().model_dump(exclude_none=True)
    if fault == "extra":
        value["embedding"] = [1, 0]
    elif fault == "no_version":
        value.pop("version")
    elif fault == "bool_version":
        value["version"] = True
    elif fault == "float_time":
        value["issued_at"] = float(value["issued_at"])
    elif fault == "long_ttl":
        value["expires_at"] += 1
    elif fault == "null_account":
        value["account_id"] = None
    elif fault == "missing_device":
        value.pop("device_id")
    elif fault == "recovery_deny":
        value.update(purpose="recovery", status="deny")
    raw = json.dumps(value, separators=(",", ":")).encode()
    if fault == "duplicate":
        raw = raw[:-1] + b',"status":"deny"}'
    signed = sign(DOMAIN + signer.key_id.encode() + b"\0" + raw, key)
    envelope = envelope.model_copy(update={"payload": encode(raw), "signature": encode(signed)})
    with pytest.raises(ValueError):
        verify_result(envelope, key.public_key(), **context())


def test_domain_separator_prevents_using_generic_signature_as_result():
    key = Ed25519PrivateKey.generate()
    envelope = ResultSigner(key).issue(claims())
    envelope = envelope.model_copy(
        update={"signature": encode(sign(decode(envelope.payload), key))}
    )
    with pytest.raises(ValueError):
        verify_result(envelope, key.public_key(), **context())


def test_private_and_public_key_loaders_are_bounded_and_curve_specific(tmp_path):
    private, public = tmp_path / "private.pem", tmp_path / "public.pem"
    key = Ed25519PrivateKey.generate()
    private.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    assert (
        load_private_key(private).public_key().public_bytes_raw()
        == load_public_key(public).public_bytes_raw()
    )
    wrong = ec.generate_private_key(ec.SECP256R1())
    private.write_bytes(
        wrong.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public.write_bytes(
        wrong.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    for fn, path in [(load_private_key, private), (load_public_key, public)]:
        with pytest.raises(ValueError):
            fn(path)
        path.write_bytes(b"x" * 4097)
        with pytest.raises(ValueError):
            fn(path)


def test_invalid_success_cannot_be_signed():
    signer = ResultSigner(Ed25519PrivateKey.generate())
    with pytest.raises(ValidationError):
        signer.issue(claims().model_copy(update={"device_id": None}))


def test_blank_example_configuration_disables_signing_without_breaking_startup():
    from vericlue_api.core.config import Settings
    from vericlue_api.core.errors import ApiError

    settings = Settings(
        _env_file=None, result_signing_key_file="", result_issuer=" ", result_audience=""
    )
    assert (
        settings.result_signing_key_file
        is settings.result_issuer
        is settings.result_audience
        is None
    )
    with pytest.raises(ApiError) as error:
        _ = settings.result_signer
    assert error.value.error_code == "result_signing_unavailable"


def test_verifier_rejects_different_key_type_without_algorithm_negotiation():
    wrong = ec.generate_private_key(ec.SECP256R1()).public_key()
    assert not verify(b"synthetic", b"x" * 64, wrong)
    with pytest.raises(ValueError):
        public_key_fingerprint(wrong)
