"""Registry schema v3: schema validation, consistency checks, and v2 regression (WP-B3)."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from assam.instruction_registry import load_registry
from assam.instruction_set import InstructionSet
from assam.ir import Instruction, Program

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assam" / "data"
CORE_V1_MNEMONICS = {
    "const", "mov", "add", "sub", "mul", "mulhu", "mulhs", "divu", "remu", "divs", "rems",
    "and", "or", "xor", "not", "shl", "shr", "sar", "seq", "slt", "sltu",
    "ld8u", "ld16u", "ld32u", "ld8s", "ld16s", "ld32s", "ld64", "st8", "st16", "st32", "st64",
    "jump", "beq", "bne", "blt", "bge", "bltu", "bgeu", "brz", "brnz", "jal", "jr", "halt", "trap", "hcall",
}  # fmt: skip


def _read(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class RegistrySchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = _read("instruction-registry-v3.schema.json")
        self.registry = _read("instruction_registry.json")
        self.validator = jsonschema.Draft202012Validator(self.schema)

    def test_schema_is_valid_and_bundled_registry_conforms(self):
        jsonschema.Draft202012Validator.check_schema(self.schema)
        self.assertEqual(list(self.validator.iter_errors(self.registry)), [])

    def test_schema_rejects_bad_entries(self):
        def mutated(change):
            registry = copy.deepcopy(self.registry)
            change(registry["instructions"][0])
            return registry

        bad = {
            "unknown trap": lambda e: e["traps"].append("nope"),
            "bad access": lambda e: e["operands"][0].update(access="rw"),
            "unknown field": lambda e: e.update(handler="x"),
            "core without width": lambda e: e.pop("width"),
            "range not decimal string": lambda e: e["operands"][0].update(min=1),
        }
        for label, change in bad.items():
            with self.subTest(label):
                self.assertTrue(
                    list(self.validator.iter_errors(mutated(change))), label
                )


class RegistryConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.registry = _read("instruction_registry.json")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def load(self, registry):
        path = Path(self.temp.name) / "registry.json"
        path.write_text(json.dumps(registry), encoding="utf-8")
        return load_registry(path)

    def entry(self, ident):
        return next(e for e in self.registry["instructions"] if e["id"] == ident)

    def test_core_v1_defines_every_instruction_including_mulh(self):
        _, _, core_v1, metadata = load_registry()
        self.assertEqual(set(core_v1), CORE_V1_MNEMONICS)
        self.assertGreaterEqual(len(core_v1), 45)
        self.assertEqual(metadata["schema_version"], 3)
        self.assertEqual(core_v1["mulhu"]["width"]["signedness"], "unsigned")
        self.assertEqual(core_v1["mulhs"]["width"]["signedness"], "signed")

    def test_core_v1_traps_and_classification(self):
        _, _, core_v1, _ = load_registry()
        for name in ("divu", "remu", "divs", "rems"):
            self.assertEqual(core_v1[name]["traps"], ["div_by_zero"])
        for name in ("ld8u", "ld64", "st8", "st64"):
            self.assertEqual(core_v1[name]["traps"], ["memory_out_of_range"])
        self.assertEqual(core_v1["jr"]["traps"], ["invalid_jump_target"])
        self.assertEqual(core_v1["hcall"]["classification"], "abi_primitive")
        ordinary = {n for n, e in core_v1.items() if e["classification"] == "ordinary"}
        self.assertEqual(ordinary, CORE_V1_MNEMONICS - {"hcall"})
        self.assertEqual(
            core_v1["ld16s"]["effects"]["memory"],
            {"read": True, "write": False, "width_bits": 16},
        )

    def test_handler_is_not_in_the_registry(self):
        for entry in self.registry["instructions"]:
            self.assertNotIn("handler", entry)
        self.assertIn("handler", InstructionSet().definition("Move"))

    def test_semantics_links_point_to_existing_documents(self):
        for entry in self.registry["instructions"]:
            if "semantics" in entry:
                self.assertTrue(
                    (ROOT / entry["semantics"].split("#")[0]).is_file(), entry["id"]
                )

    def test_inconsistent_registries_are_rejected(self):
        def duplicate_id(r):
            r["instructions"].append(copy.deepcopy(r["instructions"][0]))

        def duplicate_mapping_id(r):
            self.entry("core.sub")["target_mapping_id"] = "assam.core.1.add"

        def unknown_trap(r):
            self.entry("core.add")["traps"] = ["overflow"]

        def full_name_collision(r):
            self.entry("core.add")["full_names"] = ["Move"]

        def full_names_collide_each_other(r):
            self.entry("core.add")["full_names"] = ["Plus"]
            self.entry("core.sub")["full_names"] = ["plus"]

        def alias_collision(r):
            self.entry("draft.add")["aliases"] = ["mov"]

        def mapping_id_not_matching_mnemonic(r):
            self.entry("core.add")["target_mapping_id"] = "assam.core.1.plus"

        def full_only_with_mapping(r):
            self.entry("full.push")["target_mapping_id"] = "assam.core.draft.push"

        def bad_schema_version(r):
            r["schema_version"] = 2

        def missing_execution_entry(r):
            self.entry("full.push")["id"] = "full.pushx"

        for change in (
            duplicate_id, duplicate_mapping_id, unknown_trap, full_name_collision, full_names_collide_each_other,
            alias_collision, mapping_id_not_matching_mnemonic, full_only_with_mapping, bad_schema_version,
            missing_execution_entry,
        ):  # fmt: skip
            with self.subTest(change.__name__):
                registry = copy.deepcopy(self.registry)
                self.registry = registry
                change(registry)
                with self.assertRaises(RuntimeError):
                    self.load(registry)
                self.registry = _read("instruction_registry.json")


class FullRegressionAgainstV2Tests(unittest.TestCase):
    """The Draft/Full view of v3 must equal the frozen v2 registry (Full accept/reject is unchanged)."""

    def setUp(self):
        self.v2 = _read("instruction_registry_v2.json")
        self.definitions = InstructionSet().definitions()

    def test_every_v2_instruction_has_an_identical_v3_definition(self):
        self.assertEqual(len(self.definitions), len(self.v2["instructions"]))
        for item in self.v2["instructions"]:
            with self.subTest(item["opcode"]):
                got = self.definitions[item["opcode"].lower()]
                for key in (
                    "opcode",
                    "handler",
                    "flow",
                    "profile",
                    "target_mapping_id",
                    "operation",
                    "predicate",
                ):
                    self.assertEqual(got.get(key), item.get(key), key)
                self.assertEqual(got["operands"], tuple(item["operands"]))
                self.assertEqual(got["aliases"], tuple(item.get("aliases", [])))
                self.assertEqual(got["read_operands"], tuple(item["read_operands"]))
                self.assertEqual(got["write_operands"], tuple(item["write_operands"]))
                self.assertEqual(
                    got["data_memory_effects"], item["data_memory_effects"]
                )
                self.assertEqual(
                    got.get("integer_parameters"), item.get("integer_parameters")
                )
                expected_traps = tuple(
                    {
                        "kind": c["kind"],
                        "operand_positions": tuple(c["operand_positions"]),
                    }
                    for c in item.get("trap_conditions", [])
                )
                self.assertEqual(got["trap_conditions"], expected_traps)

    def test_names_and_aliases_resolve_the_same(self):
        instruction_set = InstructionSet()
        for item in self.v2["instructions"]:
            for name in [item["opcode"], *item.get("aliases", [])]:
                for spelling in (name, name.lower(), name.upper()):
                    self.assertEqual(
                        instruction_set.canonical_opcode(spelling),
                        item["opcode"].lower(),
                    )
        # Core v1 mnemonics that are not Draft/Full names (e.g. mulhu) stay unknown to the Full parser.
        self.assertIsNone(instruction_set.canonical_opcode("mulhu"))
        self.assertIsNone(instruction_set.canonical_opcode("ld64"))

    def test_validation_accepts_and_rejects_as_before(self):
        instruction_set = InstructionSet()
        ok = Program([Instruction("Add", ("r1", 2, 3)), Instruction("Halt", ())])
        instruction_set.validate(ok)
        instruction_set.validate(ok, profile="core")
        for opcode, operands in (
            ("Add", ("r1", 2)),
            ("Add", (1, 2, 3)),
            ("mulhu", ("r1", "r2", "r3")),
            ("Halt", ("r1",)),
        ):
            with self.subTest(opcode=opcode, operands=operands):
                with self.assertRaises(ValueError):
                    instruction_set.validate(Program([Instruction(opcode, operands)]))
        with self.assertRaisesRegex(ValueError, "outside the Assam Core profile"):
            instruction_set.validate(
                Program([Instruction("Push", (1,))]), profile="core"
            )

    def test_draft_profile_marker_is_unchanged(self):
        marker = InstructionSet.core_profile_marker()
        self.assertEqual(
            (marker.name, marker.version, marker.registry_schema_version),
            ("Assam Core", "draft", 2),
        )


if __name__ == "__main__":
    unittest.main()
