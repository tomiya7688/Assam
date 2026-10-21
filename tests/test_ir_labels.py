"""Regression tests for JSON IR label-table validation."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from assam.cli import main
from assam.ir import Program


class ProgramLabelLoadingTests(unittest.TestCase):
    def test_rejects_malformed_label_table_at_load_time(self):
        instructions = [{"opcode": "Jump", "operands": ["entry"]}, {"opcode": "Halt", "operands": []}]
        invalid_tables = (
            ([{"entry": 1}], "labels must be an object"),
            ("entry", "labels must be an object"),
            ({"": 1}, "invalid label name"),
            ({1: 1}, "invalid label name"),
            ({"entry": "1"}, "label 'entry' target must be an integer"),
            ({"entry": True}, "label 'entry' target must be an integer"),
            ({"entry": 1.0}, "label 'entry' target must be an integer"),
            ({"entry": -1}, "label 'entry' target out of range"),
            ({"entry": 2}, "label 'entry' target out of range"),
        )
        for labels, message in invalid_tables:
            with self.subTest(labels=labels):
                with self.assertRaisesRegex(ValueError, message):
                    Program.from_dict({"instructions": instructions, "labels": labels})

    def test_json_rejects_string_target_before_vm_construction(self):
        source = json.dumps({"instructions": [{"opcode": "Jump", "operands": ["entry"]}], "labels": {"entry": "0"}})
        with self.assertRaisesRegex(ValueError, "label 'entry' target must be an integer"):
            Program.from_json(source)

    def test_accepts_valid_label_and_empty_program(self):
        source = {"instructions": [{"opcode": "Jump", "operands": ["entry"]}, {"opcode": "Halt", "operands": []}], "labels": {"entry": 1}}
        self.assertEqual(Program.from_dict(source).labels, {"entry": 1})
        self.assertEqual(Program.from_json('{"instructions": [], "labels": {}}').labels, {})

    def test_cli_reports_load_error_without_python_exception(self):
        source = {"instructions": [{"opcode": "Jump", "operands": ["entry"]}], "labels": {"entry": "0"}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.assam.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                result = main(["run", str(path), "--json"])
        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("assam: error: label 'entry' target must be an integer", errors.getvalue())

    def test_non_object_program_is_a_value_error(self):
        with self.assertRaisesRegex(ValueError, "program must be an object"):
            Program.from_dict(None)
