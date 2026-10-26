"""Regression and portable conformance cases for conditional Core branches."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from assam import VM, parse_program


_CASES = (
    Path(__file__).resolve().parents[1]
    / "examples/conformance/conditional-branches.json"
)


@pytest.mark.parametrize(
    "case",
    json.loads(_CASES.read_text(encoding="utf-8"))["cases"],
    ids=lambda case: case["name"],
)
def test_shared_conditional_branch_cases(case):
    vm = VM(parse_program(case["source"]), profile="core")

    vm.run()

    assert vm.halted
    assert vm.memory == {
        int(address): value for address, value in case["expected_memory"].items()
    }
