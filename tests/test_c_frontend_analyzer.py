import sys
sys.path.insert(0, ".")
import pytest

from assam import VM, parse_program
from assam.analyzer import ProgramAnalyzer
from assam.c_frontend import CTranslator


def run_c(source):
    return VM(CTranslator().translate(source)).run()["r0"]


def test_sum_example():
    assert run_c(open("examples/sum.c").read()) == 42


@pytest.mark.parametrize("expr,expected", [
    ("1 + 2 * 3", 7),
    ("(1 + 2) * 3", 9),
    ("20 - 5 - 3", 12),
    ("17 / 5", 3),
    ("17 % 5", 2),
    ("0x10 + 1", 17),
])
def test_expression_precedence(expr, expected):
    assert run_c(f"int main(void) {{ return {expr}; }}") == expected


def test_assignment_comments_and_default_init():
    src = "int main() { /* c */ int a; int b = 4; // x\n a = b * 2; return a + b; }"
    assert run_c(src) == 12


@pytest.mark.parametrize("src", [
    "void f() {}",
    "int main(void) { int a; int a; return 0; }",
    "int main(void) { b = 1; return 0; }",
    "int main(void) { return 1; int a; }",
    "int main(void) { int a = 1; }",
    "int main(void) { while (1) {} return 0; }",
])
def test_unsupported_c_raises(src):
    with pytest.raises(ValueError):
        CTranslator().translate(src)


def test_to_source_roundtrip():
    t = CTranslator()
    program = t.translate("int main(void) { return 2 + 3; }")
    assert VM(parse_program(t.to_source(program))).run()["r0"] == 5


def test_analyzer_summary_and_unreachable():
    program = parse_program("Move r0 1\nJump end\nMove r0 2\nend:\nHalt")
    a = ProgramAnalyzer()
    report = a.analyze(program)
    assert report["instruction_count"] == 4
    assert report["register_writes"]["r0"] == 2
    assert report["unreachable_instructions"] == [2]
    assert "Unreachable instructions: 2" in a.format_text(report)


def test_analyzer_straight_line_has_one_block():
    report = ProgramAnalyzer().analyze(parse_program("Move r0 1\nAdd r1 r0 2\nHalt"))
    assert len(report["basic_blocks"]) == 1
    assert report["unreachable_instructions"] == []
    assert report["control_flow_edges"] == []
