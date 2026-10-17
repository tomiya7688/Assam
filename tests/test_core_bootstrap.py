"""Shared golden cases + Python/Go differential tests; requires a Go toolchain."""
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import core_reference as ref

CORPUS = json.loads((ROOT / "testdata/core-v1.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def runner(tmp_path_factory):
    path = tmp_path_factory.mktemp("go") / "assam-core"
    if sys.platform == "win32":
        path = path.with_suffix(".exe")
    subprocess.run(["go", "build", "-o", str(path), "./cmd/assam-core"], cwd=ROOT, check=True, timeout=120)
    return path


def execute(runner, source, budget=100):
    process = subprocess.run([str(runner), "-profile", ref.PROFILE, "-max-steps", str(budget), "-"],
                             input=source, encoding="utf-8", capture_output=True, timeout=10)
    assert process.returncode in (0, 1), process.stderr
    result = json.loads(process.stdout)
    assert process.returncode == (0 if result["status"] == "halted" else 1)
    return result


@pytest.mark.parametrize("case", CORPUS["valid"], ids=lambda c: c["name"])
def test_shared_golden(case, runner):
    code, canonical = ref.parse(case["source"], CORPUS["profile"])
    expected = ref.run(code, case["budget"])
    for key, value in case["expected"].items():
        if key == "registers":
            for reg, register_value in value.items():
                assert expected[key][int(reg)] == register_value
        else:
            assert expected[key] == value
    assert execute(runner, case["source"], case["budget"]) == expected
    assert ref.parse(canonical, ref.PROFILE)[1] == canonical
    p = subprocess.run([str(runner), "-profile", ref.PROFILE, "-canonical", "-"],
                       input=case["source"], encoding="utf-8", capture_output=True, timeout=10)
    assert p.returncode == 0, p.stderr
    assert p.stdout == canonical


@pytest.mark.parametrize("source", CORPUS["invalid"])
def test_reject_invalid(source, runner):
    with pytest.raises(ValueError):
        ref.parse(source, ref.PROFILE)
    process = subprocess.run([str(runner), "-profile", ref.PROFILE, "-"],
                             input=source, encoding="utf-8", capture_output=True, timeout=10)
    assert process.returncode == 2
    assert process.stderr
    assert not process.stdout


def test_generated_differential(runner):
    rng = random.Random(7688)
    for _ in range(100):
        lines = [f"const r{i}, {rng.getrandbits(64)}" for i in range(1, 8)]
        operations = [k for k,v in ref.REGISTRY["opcodes"].items()
                      if v["operands"] == ["write_reg", "read_reg", "read_reg"]]
        for _ in range(20):
            lines.append(f"{rng.choice(operations)} r{rng.randrange(8)}, r{rng.randrange(8)}, r{rng.randrange(8)}")
        lines.append("halt")
        source = "\n".join(lines)
        code, _ = ref.parse(source, ref.PROFILE)
        assert execute(runner, source, 28) == ref.run(code, 28)


def test_profile_and_source_limits(runner):
    for profile in ("", "full", "assam-core/v1", "assam-core/v2"):
        with pytest.raises(ValueError):
            ref.parse("halt", profile)
        process = subprocess.run([str(runner), "-profile", profile, "-"], input="halt",
                                 encoding="utf-8", capture_output=True, timeout=10)
        assert process.returncode == 2
    for source in (" " * (ref.MAX_SOURCE_BYTES + 1), "\x00halt"):
        with pytest.raises(ValueError):
            ref.parse(source, ref.PROFILE)
        p = subprocess.run([str(runner), "-profile", ref.PROFILE, "-"], input=source,
                           encoding="utf-8", capture_output=True, timeout=10)
        assert p.returncode == 2
    source = "const r1, " + "0" * 5000 + "1\nhalt"
    assert execute(runner, source) == ref.run(ref.parse(source, ref.PROFILE)[0], 100)


def test_every_registry_opcode_has_fixture():
    assert CORPUS["profile"] == ref.PROFILE
    used = set()
    for case in CORPUS["valid"]:
        _, canonical = ref.parse(case["source"], ref.PROFILE)
        used.update(line.split()[0] for line in canonical.splitlines() if not line.endswith(":"))
    assert used == set(ref.REGISTRY["opcodes"])


def test_registry_contract_is_explicitly_experimental():
    assert ref.REGISTRY["status"] == "experimental-subset"
    assert ref.REGISTRY["register_count"] == 32
    assert ref.REGISTRY["register_bits"] == 64
    assert ref.REGISTRY["required_translation_targets"] == ["x64", "arm64", "riscv"]
    for definition in ref.REGISTRY["opcodes"].values():
        assert set(definition) == {"operands", "effect", "traps"}
        assert set(definition["operands"]) <= {"write_reg", "read_reg", "immediate", "label"}
        assert definition["effect"]


def test_canonical_expansion_limit(runner):
    source = "const r1, -1\n" * 40000 + "halt"
    assert len(source) < ref.MAX_SOURCE_BYTES
    with pytest.raises(ValueError):
        ref.parse(source, ref.PROFILE)
    p = subprocess.run([str(runner), "-profile", ref.PROFILE, "-canonical", "-"], input=source,
                       encoding="utf-8", capture_output=True, timeout=10)
    assert p.returncode == 2
