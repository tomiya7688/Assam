"""Core v1 parser/emitterのgolden・負例・Full互換テスト(WP-B2)。"""

import json
import tempfile
import unittest
from pathlib import Path

from assam.cli import main
from assam.core_diagnostic import CoreParseError
from assam.core_emitter import CoreEmitter
from assam.core_parser import CoreParser
from assam.instruction_set import InstructionSet
from assam.ir import Program
from assam.parser import parse_program

GOLDEN = """entry:
    const r1, 7
    const r2, 1
loop:
    brz r1, done
    sub r1, r1, r2
    jump loop
done:
    halt
"""

# 診断コードごとの負例(code, text)
NEGATIVE = [
    ("core.syntax.unknown_opcode", "Halt\n"),
    ("core.syntax.unknown_opcode", "move r1, r2\n"),
    ("core.syntax.unknown_opcode", "bogus r1\n"),
    ("core.syntax.operand_count", "add r1, r2\n"),
    ("core.syntax.operand_count", "halt r1\n"),
    ("core.syntax.operand_kind", "const r1, r2\n"),
    ("core.syntax.operand_kind", "add r1, r2, 3\n"),
    ("core.syntax.operand_kind", "const r1, +5\n"),
    ("core.syntax.operand_kind", "const r1, 0xZZ\n"),
    ("core.syntax.separator", "add r1 r2 r3\n"),
    ("core.syntax.separator", "add r1,, r2, r3\n"),
    ("core.syntax.separator", "add r1, r2, r3,\n"),
    ("core.syntax.register_range", "mov r32, r1\n"),
    ("core.syntax.immediate_range", "const r1, 18446744073709551616\n"),
    ("core.syntax.immediate_range", "ld64 r1, r2, 2147483648\n"),
    ("core.syntax.immediate_range", "trap -1\n"),
    ("core.syntax.immediate_range", "const r1, 0x00000000000000001\n"),
    ("core.syntax.label_duplicate", "a:\n    halt\na:\n    halt\n"),
    ("core.syntax.label_undefined", "jump nowhere\n"),
    ("core.syntax.label_reserved", "add:\n    halt\n"),
    ("core.syntax.label_reserved", "r5:\n    halt\n"),
    ("core.syntax.label_dangling", "halt\nend:\n"),
    ("core.syntax.line_form", "a: halt\n"),
    ("core.syntax.line_form", "1a:\n    halt\n"),
    ("core.syntax.encoding", "\ufeffhalt\n"),
    ("core.syntax.encoding", "halt \u3042\n"),
    ("core.syntax.encoding", "halt\x00\n"),
    ("core.profile.disallowed", 'trap "x"\n'),
]


class CoreParserTest(unittest.TestCase):
    def codes(self, text):
        with self.assertRaises(CoreParseError) as ctx:
            CoreParser().parse(text)
        return [d.code for d in ctx.exception.diagnostics]

    def test_golden_round_trip(self):
        program = CoreParser().parse(GOLDEN)
        self.assertEqual(CoreEmitter().emit(program), GOLDEN)
        self.assertEqual(program.profile, InstructionSet.core_v1_profile_marker())
        self.assertEqual(program.labels, {"entry": 0, "loop": 2, "done": 5})
        again = CoreParser().parse(CoreEmitter().emit(program))
        self.assertEqual(again.instructions, program.instructions)
        self.assertEqual(again.labels, program.labels)

    def test_json_round_trip(self):
        program = CoreParser().parse(GOLDEN)
        loaded = Program.from_json(program.to_json())
        self.assertEqual(CoreEmitter().emit(loaded), GOLDEN)

    def test_normalizes_hex_comments_crlf_and_blanks(self):
        text = "  const r1, 0x2A ; c\r\n\r\n; only comment\r\n\thalt\r\n"
        self.assertEqual(
            CoreEmitter().emit(CoreParser().parse(text)),
            "    const r1, 42\n    halt\n",
        )
        self.assertIn("-1", CoreEmitter().emit(CoreParser().parse("const r1, -0x1\n")))

    def test_boundary_values_accepted(self):
        for text in (
            "const r1, 18446744073709551615\n",
            "const r1, -9223372036854775808\n",
            "const r1, 0xFFFFFFFFFFFFFFFF\n",
            "ld8u r1, r2, -2147483648\n",
            "st64 r1, r2, 2147483647\n",
            "trap 4294967295\n",
            "hcall 0\n",
            "mov r31, r0\n",
        ):
            CoreParser().parse(text)

    def test_every_negative_code_is_covered(self):
        for code, text in NEGATIVE:
            with self.subTest(code=code, text=text):
                self.assertIn(code, self.codes(text))
        documented = {
            "core.syntax.unknown_opcode", "core.syntax.operand_count",
            "core.syntax.operand_kind", "core.syntax.separator",
            "core.syntax.register_range", "core.syntax.immediate_range",
            "core.syntax.label_duplicate", "core.syntax.label_undefined",
            "core.syntax.label_reserved", "core.syntax.line_form",
            "core.syntax.encoding", "core.profile.disallowed",
        }
        self.assertTrue(documented <= {code for code, _ in NEGATIVE})

    def test_diagnostics_have_position_and_do_not_stop_at_first(self):
        with self.assertRaises(CoreParseError) as ctx:
            CoreParser().parse("halt\nbogus\nadd r1\n")
        items = ctx.exception.diagnostics
        self.assertEqual([(d.line, d.code) for d in items], [
            (2, "core.syntax.unknown_opcode"), (3, "core.syntax.operand_count")])
        self.assertEqual(items[0].source_line, "bogus")
        self.assertEqual(items[0].column, 1)
        self.assertEqual(set(items[0].to_dict()), {"code", "message", "line", "column", "source_line"})

    def test_diagnostic_limit(self):
        with self.assertRaises(CoreParseError) as ctx:
            CoreParser().parse("bogus\n" * 50)
        self.assertEqual(len(ctx.exception.diagnostics), 20)
        with self.assertRaises(CoreParseError) as ctx:
            CoreParser(max_diagnostics=3).parse("bogus\n" * 50)
        self.assertEqual(len(ctx.exception.diagnostics), 3)

    def test_emitter_rejects_non_core_program(self):
        with self.assertRaises(ValueError):
            CoreEmitter().emit(parse_program('Move r0 "a"\n'))

    def test_core_text_is_accepted_by_full_parser(self):
        source = "const r1, 7\nloop:\nbrz r1, done\nsub r1, r1, r1\njump loop\ndone:\nhalt\n"
        full = parse_program(source)
        core = CoreParser().parse(source)
        self.assertEqual(
            [i.opcode.lower() for i in full.instructions],
            [i.opcode for i in core.instructions],
        )

    def test_cli_core_v1(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "a.assam"), Path(tmp, "a.json")
            src.write_text(GOLDEN, encoding="utf-8")
            self.assertEqual(main(["json", str(src), "--profile", "core-v1", "-o", str(out)]), 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["profile"]["version"], "1")
            src.write_text("bogus\n", encoding="utf-8")
            self.assertEqual(main(["json", str(src), "--profile", "core-v1"]), 2)


if __name__ == "__main__":
    unittest.main()
