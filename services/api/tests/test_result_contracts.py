"""Result wire schema and strict Python models agree; no private extensions."""

import pytest
from contract_utils import defs, validate
from jsonschema import ValidationError

from vericlue_api.schemas.result import ResultClaims, SignedResult, SigningKey


@pytest.mark.parametrize("model", [ResultClaims, SignedResult, SigningKey])
def test_fields_match_source_contract(model):
    assert set(model.model_fields) == set(defs("result")[model.__name__]["properties"])


@pytest.mark.parametrize("extra", ["embedding", "score", "phone", "id_number"])
def test_assertion_and_public_key_reject_private_fields(extra):
    envelope = {
        "algorithm": "Ed25519",
        "key_id": "a" * 64,
        "payload": "a" * 32,
        "signature": "b" * 86,
    }
    validate(envelope, "result", "SignedResult")
    with pytest.raises(ValidationError):
        validate({**envelope, extra: "private"}, "result", "SignedResult")


@pytest.mark.parametrize("fault", ["identity", "device", "version", "purpose", "recovery_negative"])
def test_claims_contract_rejects_incomplete_or_unsupported_context(fault):
    from test_result_signing import claims

    data = claims().model_dump(exclude_none=True)
    if fault == "identity":
        data.pop("account_id")
    elif fault == "device":
        data.pop("device_id")
    elif fault == "version":
        data["version"] = True
    elif fault == "purpose":
        data["purpose"] = "onboarding"
    elif fault == "recovery_negative":
        data.update(purpose="recovery", status="deny")
    with pytest.raises(ValidationError):
        validate(data, "result", "ResultClaims")
