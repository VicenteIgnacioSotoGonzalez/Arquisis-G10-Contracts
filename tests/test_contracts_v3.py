"""E2-025: pruebas de contratos basadas en los schemas oficiales v3.0.1.

Solo verifican estructura JSON y consistencia de los fixtures. Las reglas de
mercado, el user_id del broker, la firma JWT y la autoridad wallet se prueban
en servicios de integracion, no con JSON Schema.

Ejecutar: python3 -m unittest discover -s tests -v
"""

import copy
import hashlib
import json
from pathlib import Path
import unittest
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "docs" / "schemas" / "v3"
SCHEMAS = OFFICIAL / "schemas"
EXAMPLES = ROOT / "docs" / "examples" / "v3"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class V3ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = read_json(EXAMPLES / "manifest.json")
        cls.schemas = {}
        cls.registry = Registry()
        for path in sorted(SCHEMAS.rglob("*.json")):
            schema = read_json(path)
            relative = path.relative_to(SCHEMAS).as_posix()
            cls.schemas[relative] = schema
            cls.registry = cls.registry.with_resource(
                schema["$id"], Resource.from_contents(schema)
            )
        cls.format_checker = FormatChecker()

    def errors(self, kind, payload):
        schema = self.schemas[f"{kind}.schema.json"]
        validator = Draft202012Validator(
            schema, registry=self.registry, format_checker=self.format_checker
        )
        return list(validator.iter_errors(payload))

    def fixture(self, filename):
        return read_json(EXAMPLES / "valid" / filename)

    def test_schemas_2020_12_are_well_formed(self):
        self.assertEqual(len(self.schemas), 46)
        ids = []
        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                self.assertEqual(
                    schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
                )
                Draft202012Validator.check_schema(schema)
                ids.append(schema["$id"])
        self.assertEqual(len(ids), len(set(ids)))

    def test_official_schemas_and_openapi_are_unchanged(self):
        """E2-024 guardo hashes de los archivos oficiales v3.0.1."""
        source = read_json(OFFICIAL / "SOURCE_SHA256.json")
        self.assertEqual(source["tag"], "v3.0.1")
        expected = source["files_sha256"]
        actual_paths = {
            path.relative_to(OFFICIAL).as_posix()
            for path in SCHEMAS.rglob("*.json")
        } | {"wallet.openapi.yaml"}
        self.assertEqual(actual_paths, set(expected))
        for name, digest in expected.items():
            with self.subTest(file=name):
                computed = hashlib.sha256((OFFICIAL / name).read_bytes()).hexdigest()
                self.assertEqual(computed, digest)

    def test_manifest_references_all_fixture_files(self):
        self.assertEqual(set(self.manifest), {"$comment", "valid", "invalid"})
        for category in ("valid", "invalid"):
            listed = self.manifest[category]
            actual = {path.name for path in (EXAMPLES / category).glob("*.json")}
            self.assertEqual(set(listed), actual, f"fixtures sin registrar: {category}")
            for filename, kind in listed.items():
                with self.subTest(category=category, file=filename):
                    self.assertIn(f"{kind}.schema.json", self.schemas)
        self.assertEqual(len(self.manifest["valid"]), 31)
        self.assertEqual(len(self.manifest["invalid"]), 18)

    def test_all_official_amqp_messages_have_a_valid_fixture(self):
        official_types = {
            path.stem.removesuffix(".schema")
            for path in (SCHEMAS / "amqp").glob("*.schema.json")
        }
        covered = {
            kind.removeprefix("amqp/")
            for kind in self.manifest["valid"].values()
            if kind.startswith("amqp/")
        }
        self.assertEqual(covered, official_types)

    def test_valid_fixtures_match_official_schemas(self):
        for filename, kind in self.manifest["valid"].items():
            with self.subTest(file=filename, schema=kind):
                errors = self.errors(kind, self.fixture(filename))
                self.assertFalse(errors, str(errors[0]) if errors else "")

    def test_invalid_fixtures_are_rejected(self):
        for filename, kind in self.manifest["invalid"].items():
            with self.subTest(file=filename, schema=kind):
                payload = read_json(EXAMPLES / "invalid" / filename)
                self.assertTrue(
                    self.errors(kind, payload),
                    f"{filename} fue aceptado por el schema oficial {kind}",
                )

    def test_retry_idpk_and_msgid_are_distinct_concepts(self):
        # Estructuralmente es valido reintentar con nuevo msgId y mismo idpk.
        bid = self.fixture("bid.json")
        retry = copy.deepcopy(bid)
        retry["msgId"] = str(uuid4())
        self.assertEqual(retry["idpk"], bid["idpk"])
        self.assertNotEqual(retry["msgId"], bid["msgId"])
        self.assertFalse(self.errors("amqp/bid", retry))

        # La restriccion idpk != msgId NO puede expresarse en el schema oficial.
        # Se debe rechazar en la capa de protocolo, no en estos contract tests.
        same_ids = copy.deepcopy(bid)
        same_ids["msgId"] = same_ids["idpk"]
        self.assertFalse(self.errors("amqp/bid", same_ids))

    def test_business_rules_do_not_get_misclassified_as_json_errors(self):
        bid = self.fixture("bid.json")
        bid["data"]["quantity"] = 0
        self.assertFalse(self.errors("amqp/bid", bid))

        bid["data"]["quantity"] = 7300
        bid["data"]["pricePerEnergy"] = 1
        self.assertFalse(self.errors("amqp/bid", bid))

        # Cambiar el orden temporal mantiene el formato JSON valido.
        # La autoridad sobre cierres/ventanas reside en status-statement + backend.
        status = self.fixture("status-statement.json")
        market = status["data"]["market"]
        market["lastOfferAt"], market["closesAt"] = (
            market["closesAt"], market["lastOfferAt"]
        )
        self.assertFalse(self.errors("amqp/status-statement", status))

    def test_wallet_202_is_acceptance_not_settlement(self):
        response = self.fixture("wallet-write-accepted-response.json")
        self.assertEqual(response["status"], "accepted")
        self.assertFalse(self.errors("wallet/write-accepted", response))
        response["status"] = "settled"
        self.assertTrue(self.errors("wallet/write-accepted", response))
        # El settlement real se conoce por eventos wallet/GET, no por HTTP 202.
        settled_event = self.fixture("swap-settled.json")
        self.assertFalse(self.errors("amqp/swap-settled", settled_event))

    def test_swap_expired_does_not_require_data_idpk(self):
        event = self.fixture("swap-expired.json")
        self.assertNotIn("idpk", event["data"])
        self.assertFalse(self.errors("amqp/swap-expired", event))


if __name__ == "__main__":
    unittest.main()
