import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from assam.cli import main
from assam.target_coverage import build_target_coverage_template, check_target_mappings


class _TargetMappingFixture(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.mapping_path = Path(self.temp_dir.name) / "mapping.json"
        self.registry_path = Path(self.temp_dir.name) / "registry.json"
        self.coverage_path = Path(self.temp_dir.name) / "coverage.json"
        bundled_registry = Path(__file__).resolve().parents[1] / "assam/data/instruction_registry.json"
        self.registry = json.loads(bundled_registry.read_text(encoding="utf-8"))

    def write_mapping(self, indices, hook="move"):
        table = {
            "schema_version": 1,
            "core_profile": self.registry["core_profile"],
            "registry_schema_version": self.registry["schema_version"],
            "target": {"architecture": "example-isa", "profile": "structural-example"},
            "mappings": [{
                "target_mapping_id": f"assam.core.draft.{hook}",
                "sequence": [{
                    "opcode": "example_copy",
                    "operands": [{"kind": "core_operand", "index": index} for index in indices],
                }],
            }],
        }
        self.mapping_path.write_text(json.dumps(table), encoding="utf-8")


class TargetMappingOperandReferenceTests(_TargetMappingFixture):
    def test_move_accepts_both_existing_operand_positions(self):
        self.write_mapping([0, 1])
        report = check_target_mappings(self.mapping_path)
        self.assertEqual(report["mapping_count"], 1)
        self.assertNotIn("assam.core.draft.move", report["core_ids_without_mapping"])
        self.assertIn("assam.core.draft.halt", report["core_ids_without_mapping"])

    def test_move_rejects_first_missing_position_and_larger_indices(self):
        for index in (2, 100):
            with self.subTest(index=index):
                self.write_mapping([index])
                with self.assertRaisesRegex(ValueError, "out of range.*move.*2 operand"):
                    check_target_mappings(self.mapping_path)

    def test_zero_operand_instruction_accepts_no_references_and_rejects_zero(self):
        self.write_mapping([], hook="halt")
        self.assertEqual(check_target_mappings(self.mapping_path)["mapping_count"], 1)
        self.write_mapping([0], hook="halt")
        with self.assertRaisesRegex(ValueError, "out of range.*halt.*0 operand"):
            check_target_mappings(self.mapping_path)

    def test_invalid_index_types_remain_rejected(self):
        for index in (-1, True, 1.0, "1", None):
            with self.subTest(index=index):
                self.write_mapping([index])
                with self.assertRaisesRegex(ValueError, "non-negative integer"):
                    check_target_mappings(self.mapping_path)

    def test_custom_registry_controls_operand_count(self):
        move = next(item for item in self.registry["instructions"] if item["opcode"] == "Move")
        move["operands"] = ["register", "value", "value"]
        self.registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
        self.write_mapping([2])
        self.assertEqual(check_target_mappings(self.mapping_path, self.registry_path)["mapping_count"], 1)
        move["operands"] = ["register"]
        self.registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "out of range.*1 operand"):
            check_target_mappings(self.mapping_path, self.registry_path)

    def test_malformed_registry_operands_raise_a_validation_error(self):
        move = next(item for item in self.registry["instructions"] if item["opcode"] == "Move")
        for operands in (None, "register,value", 2):
            with self.subTest(operands=operands):
                move["operands"] = operands
                self.registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
                self.write_mapping([0])
                with self.assertRaisesRegex(ValueError, "Core registry operands must be an array"):
                    check_target_mappings(self.mapping_path, self.registry_path)

    def test_unknown_hook_is_rejected(self):
        self.write_mapping([0], hook="unknown")
        with self.assertRaisesRegex(ValueError, "unknown Core target_mapping_id"):
            check_target_mappings(self.mapping_path)

    def test_cli_reports_valid_json_and_rejects_invalid_references(self):
        self.write_mapping([1])
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(["check-target-mappings", str(self.mapping_path), "--format", "json"])
        self.assertEqual(result, 0)
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(
            json.loads(output.getvalue())["validation_scope"],
            "mapping_structure_and_registry_references_only",
        )
        self.write_mapping([2])
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(["check-target-mappings", str(self.mapping_path), "--format", "json"])
        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("out of range", errors.getvalue())


class TargetMappingCoverageTests(_TargetMappingFixture):
    def write_coverage(self, hooks, architecture="example-isa", profile="structural-example", registry_path=None):
        manifest = build_target_coverage_template(architecture, profile, registry_path)
        in_scope = {f"assam.core.draft.{hook}" for hook in hooks}
        for entry in manifest["coverage"]:
            if entry["target_mapping_id"] in in_scope:
                entry["disposition"] = "in_scope"
        self.coverage_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def test_matching_coverage_reports_checked_declarations(self):
        self.write_mapping([0, 1])
        self.write_coverage(["move"])
        report = check_target_mappings(self.mapping_path, coverage_path=self.coverage_path)
        self.assertEqual(report["coverage"]["in_scope"], 1)
        self.assertEqual(report["coverage"]["out_of_scope"], len(report["core_ids_without_mapping"]))
        self.assertEqual(report["validation_scope"], "mapping_structure_registry_references_and_coverage_only")

    def test_missing_in_scope_mapping_is_rejected(self):
        self.write_mapping([0])
        self.write_coverage(["move", "add"])
        with self.assertRaisesRegex(ValueError, "missing in_scope mappings: assam.core.draft.add"):
            check_target_mappings(self.mapping_path, coverage_path=self.coverage_path)

    def test_mapping_for_out_of_scope_hook_is_rejected(self):
        self.write_mapping([0])
        self.write_coverage([])
        with self.assertRaisesRegex(ValueError, "mappings declared out_of_scope: assam.core.draft.move"):
            check_target_mappings(self.mapping_path, coverage_path=self.coverage_path)

    def test_missing_and_excluded_mappings_are_reported_together(self):
        self.write_mapping([0])
        self.write_coverage(["add"])
        with self.assertRaises(ValueError) as error:
            check_target_mappings(self.mapping_path, coverage_path=self.coverage_path)
        self.assertIn("missing in_scope mappings: assam.core.draft.add", str(error.exception))
        self.assertIn("mappings declared out_of_scope: assam.core.draft.move", str(error.exception))

    def test_target_architecture_and_profile_must_match(self):
        self.write_mapping([0])
        for architecture, profile in (("other-isa", "structural-example"), ("example-isa", "other-profile")):
            with self.subTest(architecture=architecture, profile=profile):
                self.write_coverage(["move"], architecture, profile)
                with self.assertRaisesRegex(ValueError, "target architecture/profile must match"):
                    check_target_mappings(self.mapping_path, coverage_path=self.coverage_path)

    def test_architecture_aliases_are_accepted(self):
        for architecture, alias in (("x64", " x86_64 "), ("arm64", "AArch64"), ("riscv", "RISC-V")):
            with self.subTest(architecture=architecture):
                self.write_mapping([0])
                table = json.loads(self.mapping_path.read_text(encoding="utf-8"))
                table["target"]["architecture"] = alias
                self.mapping_path.write_text(json.dumps(table), encoding="utf-8")
                self.write_coverage(["move"], architecture)
                self.assertEqual(check_target_mappings(self.mapping_path, coverage_path=self.coverage_path)["mapping_count"], 1)

    def test_coverage_manifest_validation_cannot_be_bypassed(self):
        self.write_mapping([0])
        for invalidity, message in (("missing", "missing Core IDs"), ("duplicate", "duplicate target_mapping_id"), ("reason", "requires a non-empty reason")):
            with self.subTest(invalidity=invalidity):
                manifest = self.write_coverage(["move"])
                if invalidity == "missing":
                    manifest["coverage"].pop()
                elif invalidity == "duplicate":
                    manifest["coverage"].append(manifest["coverage"][0])
                else:
                    next(entry for entry in manifest["coverage"] if entry["disposition"] == "out_of_scope")["reason"] = " "
                self.coverage_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    check_target_mappings(self.mapping_path, coverage_path=self.coverage_path)

    def test_custom_registry_is_used_for_both_mapping_and_coverage(self):
        self.registry["instructions"] = [item for item in self.registry["instructions"] if item["opcode"] == "Move"]
        self.registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
        self.write_mapping([1])
        self.write_coverage(["move"], registry_path=self.registry_path)
        report = check_target_mappings(self.mapping_path, self.registry_path, self.coverage_path)
        self.assertEqual(report["core_ids_without_mapping"], [])
        self.assertEqual(report["coverage"]["core_total"], 1)

    def test_cli_coverage_option_reports_success_and_missing_mappings(self):
        self.write_mapping([0])
        self.write_coverage(["move"])
        args = ["check-target-mappings", str(self.mapping_path), "--coverage", str(self.coverage_path)]
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(args + ["--format", "json"])
        self.assertEqual(result, 0)
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(json.loads(output.getvalue())["coverage"]["in_scope"], 1)
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(args)
        self.assertEqual(result, 0)
        self.assertEqual(errors.getvalue(), "")
        self.assertIn("coverage declarations matched", output.getvalue())
        self.write_coverage(["move", "add"])
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(args)
        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("missing in_scope mappings", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
