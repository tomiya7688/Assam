"""Malformed input corpus: users must see diagnostics, never raw host exceptions."""

import pytest

from assam import VM, parse_program
from assam.generator import generate, load
from assam.vm import VMError

HOST_ERRORS = (TypeError, KeyError, IndexError, AttributeError, ZeroDivisionError)
DIAGNOSTICS = (ValueError, VMError)

BAD_TEXT = [
    "Move",
    "Move r0",
    "Move r99 1",
    "Bogus r0",
    "Jump nowhere",
    "Add r0 1",
    "Move r0 'unterminated",
    "Move r0 1 2 3",
    "Call",
    ":\nHalt",
    "a:\na:\nHalt",
    "\x00",
    "Divide r0 1 0\nHalt",
]

BAD_JSON = [
    "not json",
    "[]",
    '{"instructions": 5}',
    '{"instructions": [5]}',
    '{"instructions": [{"opcode": 1}]}',
    '{"instructions": [{"opcode": "Halt", "operands": "x"}]}',
    '{"instructions": [{"opcode": "Halt"}], "labels": []}',
    '{"instructions": [{"opcode": "Halt"}], "labels": {"a": "x"}}',
    '{"instructions": [{"opcode": "Move", "operands": [{"a": 1}, 2]}]}',
    '{"profile": 5, "instructions": []}',
]


@pytest.mark.parametrize("source", BAD_TEXT)
def test_bad_text_reports_a_diagnostic(source):
    with pytest.raises(DIAGNOSTICS):
        VM(parse_program(source)).run(max_steps=100)


@pytest.mark.parametrize("source", BAD_JSON)
def test_bad_json_reports_a_diagnostic(source):
    with pytest.raises(DIAGNOSTICS):
        VM(load(source)).run(max_steps=100)


@pytest.mark.parametrize("source", BAD_TEXT + BAD_JSON)
def test_no_host_exception_leaks(source):
    loaders = (parse_program, load)
    for loader in loaders:
        try:
            VM(loader(source)).run(max_steps=100)
        except HOST_ERRORS as error:  # pragma: no cover - failure path
            pytest.fail(f"{loader.__name__} leaked {type(error).__name__}: {error}")
        except DIAGNOSTICS:
            pass


def test_replay_is_deterministic():
    source = "Move r0 7\nStore 10 r0\nLoad r1 10\nAdd r2 r1 r0\nHalt"
    first, second = VM(parse_program(source)), VM(load(generate(parse_program(source))))
    assert first.run() == second.run()
    assert first.memory == second.memory
    again = VM(parse_program(source))
    assert again.run() == VM(parse_program(source)).run()
