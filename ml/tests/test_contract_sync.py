"""Model Python (result.py) phải khớp hợp đồng JSON (module_result.schema.json).

Đổi một bên mà quên bên kia → test này đỏ.
"""

import json
from pathlib import Path

from vericlue_ml.common.result import ErrorCode, EvidenceType, Gate, Module, ModuleResult, Status

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "packages/contracts/schemas/module_result.schema.json").read_text(encoding="utf-8")
)
PROPS = SCHEMA["properties"]


def _enum(prop: dict) -> set:
    return {v for v in prop["enum"] if v is not None}


def test_enums_match_contract():
    assert {m.value for m in Module} == _enum(PROPS["module"])
    assert {s.value for s in Status} == _enum(PROPS["status"])
    assert {e.value for e in ErrorCode} == _enum(PROPS["error_code"])
    assert {g.value for g in Gate} == _enum(PROPS["gate"])
    assert {t.value for t in EvidenceType} == _enum(
        PROPS["evidence"]["items"]["properties"]["type"]
    )


def test_fields_match_contract():
    assert set(ModuleResult.model_fields) == set(PROPS)
    required = {n for n, f in ModuleResult.model_fields.items() if f.is_required()}
    assert required == set(SCHEMA["required"])
