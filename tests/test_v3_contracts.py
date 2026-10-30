"""Schemas y fixtures del tag oficial v3.0.2, sin consultas de red."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from uuid import uuid4
from datetime import datetime, timezone

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "docs/schemas/v3"
EXAMPLES = ROOT / "docs/examples/v3"


def _schema_registry():
    registry = Registry()
    schemas = {}
    for path in sorted(SCHEMAS.rglob("*.schema.json")):
        schema = json.loads(path.read_text())
        Draft202012Validator.check_schema(schema)
        relative = path.relative_to(SCHEMAS).as_posix()
        schemas[relative] = schema
        registry = registry.with_resource(
            schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012),
        )
    return schemas, registry


SCHEMA_MAP, REGISTRY = _schema_registry()


def validate(kind, payload):
    schema = SCHEMA_MAP[f"{kind}.schema.json"]
    Draft202012Validator(schema, registry=REGISTRY,
                          format_checker=FormatChecker()).validate(payload)


def _tokens(pointer):
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise ValueError(f"Puntero JSON inválido: {pointer}")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def _parent(document, tokens):
    value = document
    for token in tokens[:-1]:
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def _mutated(base, mutation):
    document = copy.deepcopy(base)
    for pointer, value in mutation.get("set", {}).items():
        tokens = _tokens(pointer)
        if not tokens:
            document = copy.deepcopy(value)
        else:
            parent = _parent(document, tokens)
            if isinstance(parent, list):
                parent[int(tokens[-1])] = value
            else:
                parent[tokens[-1]] = value
    for pointer in mutation.get("unset", []):
        tokens = _tokens(pointer)
        parent = _parent(document, tokens)
        if isinstance(parent, list):
            parent.pop(int(tokens[-1]))
        else:
            del parent[tokens[-1]]
    return document


class V3ContractsTests(unittest.TestCase):
    def test_pinned_official_schemas_have_exact_hashes(self):
        expected = json.loads((SCHEMAS / "SOURCE_SHA256.json").read_text())
        actual = {path.relative_to(SCHEMAS).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted(SCHEMAS.rglob("*.schema.json"))}
        self.assertEqual(actual, expected)
        self.assertEqual(len(list((SCHEMAS / "amqp").glob("*.schema.json"))), 22)

    def test_c23_amqp_identity_and_market_close_transport(self):
        for kind in ("status-statement", "distance-table", "swap-settled"):
            self.assertEqual(SCHEMA_MAP[f"amqp/{kind}.schema.json"]["x-amqp"]["userId"], "central")
        closed = SCHEMA_MAP["amqp/market-closed.schema.json"]["x-amqp"]
        self.assertEqual(closed["userId"], "none")
        self.assertEqual(closed["routingKey"], "market.closed")

    def test_all_official_valid_and_invalid_examples(self):
        valid_count = invalid_count = 0
        for path in sorted(EXAMPLES.rglob("*.json")):
            parts = path.relative_to(EXAMPLES).parts
            self.assertGreaterEqual(len(parts), 3)
            kind = "/".join(parts[:-2])
            sample = json.loads(path.read_text())
            with self.subTest(example=path.relative_to(EXAMPLES).as_posix()):
                if parts[-2] == "valid":
                    validate(kind, sample)
                    valid_count += 1
                else:
                    self.assertEqual(parts[-2], "invalid")
                    base = json.loads((path.parent / sample["base"]).read_text())
                    validate(kind, base)
                    candidate = _mutated(base, sample)
                    schema = SCHEMA_MAP[f"{kind}.schema.json"]
                    validator = Draft202012Validator(schema, registry=REGISTRY,
                                                       format_checker=FormatChecker())
                    self.assertFalse(validator.is_valid(candidate))
                    invalid_count += 1
        self.assertGreater(valid_count, 0)
        self.assertGreater(invalid_count, 0)

    def test_own_openapi_is_v3_and_exposes_market_and_audit(self):
        api = yaml.safe_load((ROOT / "docs/openapi/openapi.yaml").read_text())
        self.assertEqual(api["openapi"], "3.1.0")
        self.assertEqual(api["info"]["version"], "3.0.2")
        for route in ("/market/strategy", "/market/book", "/market/cycle-metrics/compare",
                      "/audit/intercity", "/audit/wallet-events", "/audit/reconciliations"):
            self.assertIn(route, api["paths"])
        strategy_fields = api["components"]["schemas"]["StrategyUpdateIn"]["properties"]
        self.assertIn("offerPriceOverride", strategy_fields)
        self.assertIn("offerQuantityCap", strategy_fields)

    def test_backend_ack_and_nack_emitters_validate_against_course_schemas(self):
        backend = Path(os.environ.get("ENERGYSHARK_BACKEND_ROOT", ROOT.parent / "E0-Arquisis-local"))
        connector = backend / "connector"
        if not connector.is_dir():
            self.skipTest("Checkout de backend no disponible; CI lo obtiene explícitamente")
        sys.path.insert(0, str(connector))
        try:
            from protocol.models import ProtocolEnvelope
            from protocol.responses import build_ack, build_nack
            incoming = ProtocolEnvelope(
                idpk=uuid4(), msg_id=uuid4(), type="bid",
                timestamp=datetime.now(timezone.utc), data={"offerId": "HGW-cycle-1", "quantity": 10},
                city_id="HGW", cycle_id="cycle-1",
            )
            ack = build_ack(incoming, "KLD")
            nack = build_nack(str(incoming.msg_id), "IDENTITY_MISMATCH", 403,
                              "Identidad no coincide", "KLD", cycle_id="cycle-1")
            validate("amqp/ack", ack)
            validate("amqp/nack", nack)
            self.assertEqual(ack["data"]["target"], str(incoming.msg_id))
            self.assertEqual(nack["data"]["target"], str(incoming.msg_id))
        finally:
            sys.path.remove(str(connector))


if __name__ == "__main__":
    unittest.main()
