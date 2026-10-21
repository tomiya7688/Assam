"""Tests for required-target mapping matrix checks."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from assam.cli import main
from assam.target_coverage import build_target_coverage_template, check_target_matrix


class TargetMappingMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        registry_path = Path(__file__).resolve().parents[1] / "assam/data/instruction_registry.json"
        self.registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.manifests = []
        self.mappings = []
        for architecture, alias in (("x64", "x86-64"), ("arm64", "AArch64"), ("riscv", "RISC-V")):
            self.write_pair(architecture, alias=alias)

    def write_pair(self, architecture, profile="structural-example", alias=None, registry_path=None):
        prefix = f"{len(self.manifests)}-{architecture}"
        manifest_path = self.root / f"{prefix}-coverage.json"
        mapping_path = self.root / f"{prefix}-mapping.json"
        manifest = build_target_coverage_template(architecture, profile, registry_path)
        for entry in manifest["coverage"]:
            if entry["target_mapping_id"] == "assam.core.draft.move":
                entry["disposition"] = "in_scope"
        table = {
            "schema_version": 1,
            "core_profile": self.registry["core_profile"],
            "registry_schema_version": self.registry["schema_version"],
            "target": {"architecture": alias or architecture, "profile": profile},
            "mappings": [{
                "target_mapping_id": "assam.core.draft.move",
                "sequence": [{
                    "opcode": "example_copy",
                    "operands": [{"kind": "core_operand", "index": index} for index in (0, 1)],
                }],
            }],
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        mapping_path.write_text(json.dumps(table), encoding="utf-8")
        self.manifests.append(manifest_path)
        self.mappings.append(mapping_path)

    def test_mapping_order_and_architecture_aliases_do_not_affect_pairing(self):
        report = check_target_matrix(self.manifests, mapping_paths=reversed(self.mappings))
        self.assertEqual(report["mapping_table_count"], 3)
        self.assertEqual(report["architectures"], ["arm64", "riscv", "x64"])
        self.assertEqual(report["validation_scope"], "mapping_matrix_structure_registry_references_and_coverage_only")
        self.assertEqual([item["coverage"]["architecture"] for item in report["mappings"]], ["arm64", "riscv", "x64"])

    def test_missing_required_architecture_is_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing required target architecture declarations: riscv"):
            check_target_matrix(self.manifests[:2], mapping_paths=self.mappings[:2])

    def test_missing_mapping_table_identifies_target_and_profile(self):
        with self.assertRaisesRegex(ValueError, "missing target mapping tables: riscv/structural-example"):
            check_target_matrix(self.manifests, mapping_paths=self.mappings[:2])

    def test_explicit_empty_mapping_set_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing target mapping tables"):
            check_target_matrix(self.manifests, mapping_paths=[])

    def test_duplicate_alias_mapping_tables_are_rejected(self):
        table = json.loads(self.mappings[0].read_text(encoding="utf-8"))
        table["target"]["architecture"] = " x86_64 "
        duplicate_path = self.root / "duplicate.json"
        duplicate_path.write_text(json.dumps(table), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate target mapping table for x64/structural-example"):
            check_target_matrix(self.manifests, mapping_paths=self.mappings + [duplicate_path])

    def test_unmatched_architecture_or_profile_is_rejected(self):
        original = json.loads(self.mappings[0].read_text(encoding="utf-8"))
        for field, value in (("architecture", "other-isa"), ("profile", "other-profile")):
            with self.subTest(field=field):
                table = json.loads(json.dumps(original))
                table["target"][field] = value
                self.mappings[0].write_text(json.dumps(table), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "mapping table has no matching coverage manifest"):
                    check_target_matrix(self.manifests, mapping_paths=self.mappings)

    def test_missing_sequence_error_identifies_affected_target(self):
        manifest = json.loads(self.manifests[0].read_text(encoding="utf-8"))
        next(entry for entry in manifest["coverage"] if entry["target_mapping_id"] == "assam.core.draft.add")["disposition"] = "in_scope"
        self.manifests[0].write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "target x64/structural-example: missing in_scope mappings: assam.core.draft.add"):
            check_target_matrix(self.manifests, mapping_paths=self.mappings)

    def test_mapping_operand_validation_is_preserved(self):
        table = json.loads(self.mappings[2].read_text(encoding="utf-8"))
        table["mappings"][0]["sequence"][0]["operands"][0]["index"] = 2
        self.mappings[2].write_text(json.dumps(table), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "mapping table .*riscv-mapping.json: .*out of range"):
            check_target_matrix(self.manifests, mapping_paths=self.mappings)

    def test_custom_architectures_and_multiple_profiles_remain_supported(self):
        self.write_pair("example-fpga")
        self.write_pair("x64", profile="another-profile")
        report = check_target_matrix(self.manifests, mapping_paths=self.mappings)
        self.assertEqual(report["mapping_table_count"], 5)
        self.assertIn("example-fpga", report["architectures"])

    def test_custom_registry_is_shared_by_all_pairs(self):
        self.registry["instructions"] = [entry for entry in self.registry["instructions"] if entry["opcode"] == "Move"]
        registry_path = self.root / "registry.json"
        registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
        self.manifests.clear()
        self.mappings.clear()
        for architecture in ("x64", "arm64", "riscv"):
            self.write_pair(architecture, registry_path=registry_path)
        report = check_target_matrix(self.manifests, registry_path, self.mappings)
        self.assertTrue(all(item["coverage"]["core_total"] == 1 for item in report["mappings"]))
        self.assertTrue(all(item["core_ids_without_mapping"] == [] for item in report["mappings"]))

    def test_without_mapping_option_report_remains_declaration_only(self):
        report = check_target_matrix(self.manifests)
        self.assertEqual(report["validation_scope"], "coverage_declarations_only")
        self.assertNotIn("mappings", report)

    def test_cli_checks_all_pairs_and_reports_json_text_and_errors(self):
        args = ["check-target-matrix", *map(str, self.manifests)]
        mapping_args = [part for path in reversed(self.mappings) for part in ("--mapping", str(path))]
        for output_format in ("json", "text"):
            with self.subTest(output_format=output_format):
                output, errors = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    result = main(args + mapping_args + ["--format", output_format])
                self.assertEqual(result, 0)
                self.assertEqual(errors.getvalue(), "")
                if output_format == "json":
                    self.assertEqual(json.loads(output.getvalue())["mapping_table_count"], 3)
                else:
                    self.assertIn("3 mapping table(s) matched", output.getvalue())
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(args + ["--mapping", str(self.mappings[0])])
        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("missing target mapping tables", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
