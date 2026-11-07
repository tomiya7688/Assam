"""Typed operands and string literals (WP-B1, issue #10)."""

import json
import unittest

from assam import VM, parse_program
from assam.ir import (
    Immediate,
    Instruction,
    Program,
    Register,
    StringLiteral,
    Symbol,
    coerce_operand,
)
from assam.parser import ParseError


def run_r0(source):
    return VM(parse_program(source)).run()["r0"]


class StringLiteralTests(unittest.TestCase):
    def test_semicolon_inside_quotes_is_data(self):
        self.assertEqual(run_r0('Move r0 "a;b"\nHalt'), "a;b")

    def test_hash_inside_quotes_is_data(self):
        self.assertEqual(run_r0('Move r0 "a#b"\nHalt'), "a#b")

    def test_comment_after_literal_is_ignored(self):
        self.assertEqual(run_r0('Move r0 "x" ; comment "y"\nHalt'), "x")

    def test_numeric_looking_string_is_not_an_integer(self):
        value = run_r0('Move r0 "123"\nHalt')
        self.assertEqual(value, "123")
        self.assertIsInstance(value, str)

    def test_register_looking_string_is_not_a_register(self):
        self.assertEqual(run_r0('Move r0 "r1"\nHalt'), "r1")

    def test_empty_string_is_preserved(self):
        self.assertEqual(run_r0('Move r0 ""\nHalt'), "")

    def test_escapes(self):
        self.assertEqual(run_r0('Move r0 "\\"\\\\\\n\\t\\r\\x41"\nHalt'), '"\\\n\t\rA')

    def test_undefined_escape_is_rejected(self):
        with self.assertRaisesRegex(ParseError, "unknown escape"):
            parse_program('Move r0 "\\q"\nHalt')

    def test_unterminated_literal_is_rejected(self):
        with self.assertRaisesRegex(ParseError, "unterminated"):
            parse_program('Move r0 "abc\nHalt')

    def test_literal_must_be_followed_by_separator(self):
        with self.assertRaisesRegex(ParseError, "separator"):
            parse_program('Move r0 "text"r1\nHalt')
        self.assertEqual(run_r0('Move r0 "text",\nHalt'), "text")

    def test_bad_hex_escape_is_rejected(self):
        with self.assertRaisesRegex(ParseError, r"\\x"):
            parse_program('Move r0 "\\xZZ"\nHalt')

    def test_parsed_operands_have_kinds(self):
        program = parse_program('Move r1 42\nMove r0 "r1"\nHalt')
        self.assertEqual(program.instructions[0].operands, (Register(1), Immediate(42)))
        self.assertEqual(
            program.instructions[1].operands, (Register(0), StringLiteral("r1"))
        )


class OperandJsonTests(unittest.TestCase):
    SOURCE = 'Move r0 "a;b#"\nMove r1 ""\nMove r2 "123"\nMove r3 -7\nHalt'

    def test_json_round_trip_keeps_kinds(self):
        program = parse_program(self.SOURCE)
        restored = Program.from_json(program.to_json())
        self.assertEqual(
            [(x.opcode, x.operands) for x in restored.instructions],
            [(x.opcode, x.operands) for x in program.instructions],
        )
        self.assertEqual(VM(restored).run()["r2"], "123")
        self.assertEqual(VM(restored).run()["r0"], "a;b#")

    def test_tagged_json_shape(self):
        value = json.loads(parse_program('Move r0 "x"\nHalt').to_json())
        self.assertEqual(value["schema_version"], 2)
        self.assertEqual(
            value["instructions"][0]["operands"],
            [{"kind": "register", "index": 0}, {"kind": "string", "value": "x"}],
        )

    def test_v2_rejects_untagged_operand(self):
        source = {
            "schema_version": 2,
            "instructions": [{"opcode": "Move", "operands": ["r0", 1]}],
        }
        with self.assertRaises(ValueError):
            Program.from_dict(source)

    def test_v1_ir_is_normalized(self):
        source = {
            "instructions": [
                {"opcode": "Move", "operands": ["r0", "123"]},
                {"opcode": "Move", "operands": ["r1", 5]},
                {"opcode": "Move", "operands": ["r2", "a b"]},
                {"opcode": "Halt", "operands": []},
            ]
        }
        program = Program.from_dict(source)
        self.assertEqual(
            program.instructions[0].operands, (Register(0), StringLiteral("123"))
        )
        self.assertEqual(program.instructions[1].operands, (Register(1), Immediate(5)))
        self.assertEqual(
            program.instructions[2].operands, (Register(2), StringLiteral("a b"))
        )
        self.assertEqual(run_r0(program_to_text(program)), "123")

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            Program.from_dict(
                {
                    "schema_version": 2,
                    "instructions": [
                        {"opcode": "Move", "operands": [{"kind": "float"}]}
                    ],
                }
            )

    def test_extra_keys_in_tagged_operand_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unexpected keys"):
            Program.from_dict(
                {
                    "schema_version": 2,
                    "instructions": [
                        {
                            "opcode": "Move",
                            "operands": [
                                {"kind": "register", "index": 0, "extra": 1},
                                {"kind": "immediate", "value": 1},
                            ],
                        }
                    ],
                }
            )

    def test_missing_key_in_tagged_operand_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing keys"):
            Program.from_dict(
                {
                    "schema_version": 2,
                    "instructions": [
                        {"opcode": "Move", "operands": [{"kind": "register"}]}
                    ],
                }
            )

    def test_unsupported_schema_version_is_rejected(self):
        with self.assertRaises(ValueError):
            Program.from_dict({"schema_version": 3, "instructions": []})


class OperandModelTests(unittest.TestCase):
    def test_register_text(self):
        self.assertEqual(str(Register(31)), "r31")

    def test_string_text_is_quoted_and_escaped(self):
        self.assertEqual(str(StringLiteral('a"b\\')), '"a\\"b\\\\"')

    def test_python_values_are_coerced(self):
        self.assertEqual(coerce_operand("r4"), Register(4))
        self.assertEqual(coerce_operand(3), Immediate(3))
        self.assertEqual(coerce_operand("loop"), Symbol("loop"))
        self.assertEqual(
            Instruction("Move", ("r0", 1)).operands, (Register(0), Immediate(1))
        )

    def test_symbol_cannot_look_like_a_register(self):
        with self.assertRaises(ValueError):
            Symbol("r5")

    def test_register_index_must_be_non_negative(self):
        with self.assertRaises(ValueError):
            Register(-1)


class RegisterRangeTests(unittest.TestCase):
    def test_r31_is_accepted_and_r32_is_rejected(self):
        self.assertEqual(run_r0("Move r31 9\nMove r0 r31\nHalt"), 9)
        with self.assertRaisesRegex(ValueError, "operand 1"):
            VM(parse_program("Move r32 1\nHalt"))


class CoreProfileOperandTests(unittest.TestCase):
    def test_core_rejects_string_literal(self):
        program = parse_program('Move r0 "x"\nHalt')
        with self.assertRaisesRegex(ValueError, "Core profile"):
            VM(program, profile="core")

    def test_core_accepts_registers_and_immediates(self):
        program = parse_program("Move r0 7\nHalt")
        self.assertEqual(VM(program, profile="core").run()["r0"], 7)

    def test_core_rejects_bare_word_as_value(self):
        program = parse_program("Move r0 word\nHalt")
        with self.assertRaisesRegex(ValueError, "Core profile"):
            VM(program, profile="core")

    def test_full_accepts_bare_word_as_value(self):
        self.assertEqual(run_r0("Move r0 word\nHalt"), "word")


def program_to_text(program):
    lines = []
    for instruction in program.instructions:
        operands = " ".join(str(x) for x in instruction.operands)
        lines.append(
            instruction.opcode if not operands else f"{instruction.opcode} {operands}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    unittest.main()
