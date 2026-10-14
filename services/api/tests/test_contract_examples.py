"""Mọi ví dụ trong packages/contracts/examples phải khớp schema; tên file: <schema>.<Def>[.<biến thể>].json."""

from __future__ import annotations

import json

import pytest
from contract_utils import EXAMPLES_DIR, defs, validate

FILES = sorted(EXAMPLES_DIR.glob("*.json"))
FORBIDDEN_FOR_CITIZEN = ("score", "prob_attack", "gate", "giả mạo", "deepfake")


def _target(name: str) -> tuple[str, str | None]:
    parts = name.removesuffix(".json").split(".")
    schema = parts[0]
    if schema == "module_result":
        return schema, None
    return schema, parts[1]


def test_examples_exist():
    assert FILES, "chưa có ví dụ nào"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_example_matches_schema(path):
    schema, def_name = _target(path.name)
    if def_name is not None:
        assert def_name in defs(schema), f"{path.name}: không có $defs.{def_name}"
    validate(json.loads(path.read_text(encoding="utf-8")), schema, def_name)


@pytest.mark.parametrize(
    "path", [p for p in FILES if p.name.startswith("session.")], ids=lambda p: p.name
)
def test_session_examples_leak_nothing(path):
    text = path.read_text(encoding="utf-8").lower()
    for word in FORBIDDEN_FOR_CITIZEN:
        assert word not in text


def test_review_case_example_has_no_score():
    text = (EXAMPLES_DIR / "review.ReviewCase.json").read_text(encoding="utf-8")
    assert "score" not in text and "prob_attack" not in text


def test_every_response_def_has_an_example():
    wanted = {
        "session": [
            "CreateSessionResponse",
            "Signals",
            "StepAck",
            "FinalizeResponse",
            "VoiceResponse",
            "ErrorResponse",
        ],
        "review": [
            "ReviewCaseList",
            "ReviewCase",
            "InitialDecisionRequest",
            "ReviewAiOpinion",
            "FinalDecisionRequest",
            "DecisionResponse",
        ],
        "forensic": ["JobCreated", "ForensicJob", "VerifyRequest", "VerifyResponse"],
    }
    have = {_target(p.name) for p in FILES}
    for schema, names in wanted.items():
        for name in names:
            assert (schema, name) in have, f"thiếu ví dụ {schema}.{name}"
