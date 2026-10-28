"""Public browser-holder vector is a real Python signature over synthetic claims only."""

import base64
import json
from pathlib import Path

from contract_utils import validate
from cryptography.hazmat.primitives.serialization import load_der_public_key

from vericlue_api.core.signing import verify_result
from vericlue_api.schemas.result import SignedResult, SigningKey


def test_browser_holder_source_vector_matches_python_result_profile():
    path = (
        Path(__file__).resolve().parents[3]
        / "packages/contracts/test-vectors/holder-source-public-v1.json"
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    pin = SigningKey.model_validate(value["result_key"])
    envelope = SignedResult.model_validate(value["result"])
    expected = value["expected"]
    validate(expected, "credential", "HolderExpectedContext")
    claims = verify_result(
        envelope,
        load_der_public_key(base64.b64decode(pin.public_key_spki)),
        **{k: expected[k] for k in ("issuer", "audience", "session_id", "nonce", "purpose")},
        now=value["now"],
    )
    assert claims.status == "pass"
    assert claims.account_id == expected["account_id"] and claims.device_id == expected["device_id"]
    assert pin.key_id == envelope.key_id
    assert "secret_key" not in value and "holder_secret" not in value
