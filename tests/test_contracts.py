"""Ejecutar: python -m unittest discover -s tests -v (requiere jsonschema[format])."""
import copy
import json
from pathlib import Path
import unittest
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "docs/schemas/v2"
REGISTRY = Registry().with_resources([
    (path.as_uri(), Resource.from_contents(json.loads(path.read_text())))
    for path in SCHEMAS.glob("*.json")
])


def validate(payload):
    Draft202012Validator({"$ref": (SCHEMAS / f"{payload['type']}.schema.json").as_uri()},
        registry=REGISTRY, format_checker=FormatChecker()).validate(payload)


class ContractsTests(unittest.TestCase):
    def test_all_schemas_and_examples(self):
        for path in SCHEMAS.glob("*.json"):
            Draft202012Validator.check_schema(json.loads(path.read_text()))
        for path in (ROOT / "docs/examples/v2/valid").glob("*.json"):
            with self.subTest(example=path.name):
                validate(json.loads(path.read_text()))

    def test_early_error_codes_and_opens_at(self):
        sample = json.loads((ROOT / "docs/examples/v2/valid/error-report-too-early-425.json").read_text())
        for code in (422, 425):
            sample["code"] = code
            validate(sample)
        sample["code"] = 409
        with self.assertRaises(ValidationError):
            validate(sample)
        sample["code"] = 425
        del sample["data"]["opensAt"]
        with self.assertRaises(ValidationError):
            validate(sample)
        sample["data"]["opensAt"] = "2026-10-07T12:00:00"
        with self.assertRaises(ValidationError):
            validate(sample)
        sample["data"]["opensAt"] = "2026-10-07T12:00:00Z"
        sample["type"] = "nack"
        with self.assertRaises(ValidationError):
            validate(sample)

    def test_report_requires_cycle_and_allows_distinct_corrections(self):
        sample = json.loads((ROOT / "docs/examples/v2/valid/negotiation-report.json").read_text())
        validate(sample)
        corrected = copy.deepcopy(sample)
        corrected.update(idpk=str(uuid4()), msgId=str(uuid4()))
        corrected["data"]["budgetBalance"] -= 10
        validate(corrected)
        del sample["cycleId"]
        with self.assertRaises(ValidationError):
            validate(sample)

    def test_penalty_stays_optional_and_opaque(self):
        #Los valores sintéticos comprueban tolerancia; no describen mensajes reales del broker.
        sample = json.loads((ROOT / "docs/examples/v2/valid/transfer.json").read_text())
        validate(sample)
        for value in [None, 50000, {"unknown": "shape"}, ["opaque"]]:
            sample["data"]["penalty"] = value
            validate(sample)


    def test_requests_are_cycle_free_and_ask_is_open(self):
        sample = json.loads((ROOT / 'docs/examples/v2/valid/request.json').read_text())
        sample['data']['ask'] = 'future-information'
        validate(sample)
        sample['cycleId'] = 'opaque'
        with self.assertRaises(ValidationError):
            validate(sample)

    def test_distance_table_requires_central(self):
        sample = json.loads((ROOT / 'docs/examples/v2/valid/distance-table.json').read_text())
        validate(sample)
        sample.pop('sender')
        sample['cityId'] = 'KLD'
        with self.assertRaises(ValidationError):
            validate(sample)

    def test_distance_table_observed_shape_and_optional_metadata(self):
        #Envelope productivo informado por el usuario; ids y distancias ilustrativos.
        sample = json.loads((ROOT / 'docs/examples/v2/valid/distance-table.json').read_text())
        self.assertIsNone(sample['cityId'])
        self.assertEqual(sample['sender'], 'central')
        self.assertEqual(sample['cycleId'], 'cycle-248784')
        self.assertEqual(sample['timestamp'], '2026-10-05T23:40:04.832000Z')
        for omit in ((), ('cityId',), ('cycleId',), ('cityId', 'cycleId')):
            variant = copy.deepcopy(sample)
            for key in omit:
                variant.pop(key)
            with self.subTest(omitted=omit):
                validate(variant)
        for field in ('idpk', 'msgId', 'type', 'timestamp', 'sender'):
            variant = copy.deepcopy(sample)
            variant.pop(field)
            # Usar el schema conocido incluso cuando falta el campo type.
            validator = Draft202012Validator(
                {'$ref': (SCHEMAS / 'distance-table.schema.json').as_uri()},
                registry=REGISTRY, format_checker=FormatChecker())
            with self.subTest(missing=field), self.assertRaises(ValidationError):
                validator.validate(variant)
        sample['cityId'] = 'KLD'
        with self.assertRaises(ValidationError):
            validate(sample)

    def test_invalid_examples(self):
        for path in (ROOT / 'docs/examples/v2/invalid').glob('*.json'):
            with self.subTest(example=path.name), self.assertRaises(ValidationError):
                validate(json.loads(path.read_text()))
