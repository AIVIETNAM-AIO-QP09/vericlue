"""Hợp đồng trong packages/contracts phải là JSON Schema hợp lệ, và ví dụ (nếu có) phải khớp schema."""

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = sorted((ROOT / "packages" / "contracts" / "schemas").glob("*.schema.json"))
EXAMPLES = sorted((ROOT / "packages" / "contracts" / "examples").glob("*.json"))


@pytest.mark.parametrize("path", SCHEMAS, ids=lambda p: p.name)
def test_schema_is_valid(path):
    jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_module_result_rejects_unknown_field():
    schema = json.loads(
        (ROOT / "packages/contracts/schemas/module_result.schema.json").read_text(encoding="utf-8")
    )
    ok = {"module": "face_pad", "model_version": "mock@0.1", "status": "ok", "latency_ms": 3}
    jsonschema.validate(ok, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(ok | {"tam_thoi": 1}, schema)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_matches_schema(path):
    """Ví dụ đặt tên <schema>.<tên>.json, ví dụ module_result.genuine.json (thêm ở PLAT-04)."""
    schema_name = path.name.split(".")[0]
    schema = json.loads(
        (ROOT / f"packages/contracts/schemas/{schema_name}.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), schema)
