"""Nạp JSON Schema trong packages/contracts và validate dữ liệu theo tên $defs."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = ROOT / "packages" / "contracts" / "schemas"
EXAMPLES_DIR = ROOT / "packages" / "contracts" / "examples"


@cache
def _schemas() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        out[path.name.removesuffix(".schema.json")] = json.loads(path.read_text(encoding="utf-8"))
    return out


@cache
def _registry() -> Registry:
    registry: Registry = Registry()
    for schema in _schemas().values():
        registry = registry.with_resource(
            schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)
        )
    return registry


def validator(schema_name: str, def_name: str | None = None) -> Draft202012Validator:
    """Validator cho cả schema (`def_name=None`) hoặc một khóa trong `$defs`."""
    schema = _schemas()[schema_name]
    target = schema if def_name is None else {"$ref": f"{schema['$id']}#/$defs/{def_name}"}
    return Draft202012Validator(target, registry=_registry())


def validate(data: Any, schema_name: str, def_name: str | None = None) -> None:
    validator(schema_name, def_name).validate(data)


def defs(schema_name: str) -> dict[str, Any]:
    return _schemas()[schema_name].get("$defs", {})
