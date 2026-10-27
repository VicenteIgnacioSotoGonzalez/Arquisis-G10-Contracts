#!/usr/bin/env python3
"""Chequeo local E2-024 de fixtures, no reemplaza contract tests E2-025 en CI."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "docs/schemas/v3/schemas"
EXAMPLES = ROOT / "docs/examples/v3"
MANIFEST = json.loads((EXAMPLES / "manifest.json").read_text(encoding="utf-8"))
registry = Registry()
for path in SCHEMAS.rglob("*.json"):
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))

failures = []
for expected in ("valid", "invalid"):
    for fixture, name in MANIFEST[expected].items():
        schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
        obj = json.loads((EXAMPLES / expected / fixture).read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema, registry=registry, format_checker=FormatChecker()).iter_errors(obj))
        if bool(errors) == (expected == "valid"):
            failures.append(f"{expected}/{fixture}: " + (str(errors[0]).splitlines()[0] if errors else "deberia ser invalido"))

for failure in failures:
    print("FAIL:", failure)
print(f"Schemas oficiales: {len(list(SCHEMAS.rglob('*.json')))} | fixtures validos: {len(MANIFEST['valid'])} | invalidos: {len(MANIFEST['invalid'])} | fallos: {len(failures)}")
raise SystemExit(1 if failures else 0)
