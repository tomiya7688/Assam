"""CLI smoke: each command works on the shipped examples; errors exit non-zero without a traceback."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "assam.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_run_example():
    result = cli("run", "examples/sum.assam")
    assert result.returncode == 0, result.stderr
    assert "42" in result.stdout


def test_json_core_profile():
    result = cli("json", "examples/sum.assam", "--profile", "core")
    assert result.returncode == 0, result.stderr
    assert '"opcode"' in result.stdout


def test_from_c_example():
    result = cli("from-c", "examples/sum.c")
    assert result.returncode == 0, result.stderr
    assert "Halt" in result.stdout


def test_analyze_example():
    result = cli("analyze", "examples/sum.assam", "--format", "json")
    assert result.returncode == 0, result.stderr
    assert '"instruction_count"' in result.stdout


def test_missing_file_is_a_diagnostic_not_a_traceback():
    result = cli("run", "does-not-exist.assam")
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert result.stderr.startswith("assam: error:")
