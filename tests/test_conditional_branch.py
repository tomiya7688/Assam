"""条件分岐のconformanceケース(Full VM)を共通runnerで検査する(#8)。"""

from __future__ import annotations

from pathlib import Path

import pytest

from assam.conformance_case import ConformanceCase

_CASES = Path(__file__).resolve().parents[1] / "examples/conformance/cases"
_BRANCH = sorted(p for p in _CASES.glob("full-branch-*.json"))


@pytest.mark.parametrize("path", _BRANCH, ids=lambda p: p.stem)
def test_shared_conditional_branch_cases(path):
    from assam.conformance_runner import ConformanceRunner

    result = ConformanceRunner().run_case(ConformanceCase.load(path))

    assert result["status"] == "passed", result
