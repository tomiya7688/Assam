"""Memory golden vectors, host/guest error boundaries, and differential tests."""
import json
import random
import subprocess

import pytest

# Reuse the exact same build fixture and shared reference module as draft.1.
from test_core_bootstrap import CORPUS as BASE_CORPUS, ROOT, ref, runner

CORPUS = json.loads((ROOT / "testdata/core-memory.json").read_text(encoding="utf-8"))


def invoke(runner, source, initial=b"", budget=100, *, dump=True, profile=ref.MEMORY_PROFILE):
    args = [str(runner), "-profile", profile, "-max-steps", str(budget),
            "-memory-bytes", str(len(initial)), "-memory-hex", initial.hex()]
    if dump:
        args.append("-dump-memory")
    return subprocess.run(args + ["-"], input=source, encoding="utf-8",
                          capture_output=True, timeout=10)


def differential(runner, source, initial=b"", budget=100):
    code, canonical = ref.parse(source, ref.MEMORY_PROFILE)
    expected = ref.run_memory(code, budget, initial)
    process = invoke(runner, source, initial, budget)
    assert process.returncode == (0 if expected["status"] == "halted" else 1), process.stderr
    actual = json.loads(process.stdout)
    assert actual == expected
    assert ref.parse(canonical, ref.MEMORY_PROFILE)[1] == canonical
    return actual


@pytest.mark.parametrize("case", CORPUS["valid"], ids=lambda c: c["name"])
def test_memory_golden(case, runner):
    assert CORPUS["profile"] == ref.MEMORY_PROFILE
    initial = bytes.fromhex(case["initial_memory_hex"])
    actual = differential(runner, case["source"], initial, case["budget"])
    for key, value in case["expected"].items():
        if key == "registers":
            for reg, register_value in value.items():
                assert actual[key][int(reg)] == register_value
        else:
            assert actual[key] == value
    assert actual["memory_hex"] == case["expected_memory_hex"]
    code, canonical = ref.parse(case["source"], ref.MEMORY_PROFILE)
    assert ref.run_memory(code, case["budget"], initial) == actual
    process = subprocess.run([str(runner), "-profile", ref.MEMORY_PROFILE, "-canonical", "-"],
                             input=case["source"], encoding="utf-8", capture_output=True, timeout=10)
    assert process.returncode == 0, process.stderr
    assert process.stdout == canonical
    normalized = differential(runner, canonical, initial, case["budget"])
    actual["line"] = normalized["line"] = 0
    assert actual == normalized


@pytest.mark.parametrize("source", CORPUS["invalid"])
def test_memory_input_rejected(source, runner):
    with pytest.raises(ValueError):
        ref.parse(source, ref.MEMORY_PROFILE)
    process = invoke(runner, source)
    assert process.returncode == 2
    assert process.stderr and not process.stdout


@pytest.mark.parametrize("case", BASE_CORPUS["valid"], ids=lambda c: c["name"])
def test_draft1_behavior_preserved_in_draft2(case, runner):
    old, _ = ref.parse(case["source"], ref.PROFILE)
    actual = differential(runner, case["source"], b"", case["budget"])
    assert actual.pop("memory_hex") == ""
    assert actual == ref.run(old, case["budget"])


@pytest.mark.parametrize("opcode", list(ref.MEMORY_EXTENSION["opcodes"]))
def test_memory_not_silently_added_to_draft1(opcode, runner):
    source = f"{opcode} r1, r0\nhalt"
    with pytest.raises(ValueError):
        ref.parse(source, ref.PROFILE)
    process = subprocess.run([str(runner), "-profile", ref.PROFILE, "-"],
                             input=source, encoding="utf-8", capture_output=True, timeout=10)
    assert process.returncode == 2 and not process.stdout


def test_memory_full_register_and_bytes_differential(runner):
    rng = random.Random(7688)
    operations = list(ref.MEMORY_EXTENSION["opcodes"].items())
    # Mix reads/writes with valid, boundary, and 64-bit-unrepresentable-host addresses.
    for _ in range(250):
        size = rng.randrange(0, 65)
        initial = rng.randbytes(size)
        lines = []
        for _ in range(12):
            op, definition = rng.choice(operations)
            width = definition["memory"]["bytes"]
            address = rng.choice([0, max(0, size - width), size, rng.randrange(80),
                                  1 << 32, ref.MASK, ref.MASK - width + 1])
            lines.extend([f"const r1, {address}", f"const r2, {rng.getrandbits(64)}"])
            if definition["effect"] == "store":
                lines.append(f"{op} r1, r{rng.choice([0, 1, 2])}")
            else:
                lines.append(f"{op} r{rng.choice([0, 1, 2, 3])}, r1")
        lines.append("halt")
        differential(runner, "\n".join(lines), initial, rng.choice([0, 1, 3, 5, 36, 37, 100]))


def test_memory_all_width_boundary_grid(runner):
    for opcode, definition in ref.MEMORY_EXTENSION["opcodes"].items():
        width = definition["memory"]["bytes"]
        for size in (0, width - 1, width, width + 1):
            for address in sorted({0, 1, size, ref.MASK, 1 << 32}):
                initial = b"\xa5" * size
                source = f"const r1, {address}\nconst r2, 42\n"
                source += f"{opcode} " + ("r2, r1" if definition["effect"] == "load" else "r1, r2") + "\nhalt"
                result = differential(runner, source, initial, 4)
                invalid = address + width > size
                assert result["status"] == ("trap" if invalid else "halted")
                if invalid:
                    assert result["code"] == "memory_out_of_bounds"
                    assert result["registers"][2] == "0x000000000000002a"
                    assert result["memory_hex"] == initial.hex()


@pytest.mark.parametrize("flags", [
    ["-memory-bytes", "-1"],
    ["-memory-bytes", str(ref.MAX_MEMORY_BYTES + 1)],
    ["-memory-bytes", str(1 << 64)],
    ["-memory-bytes", str(ref.MASK)],
    ["-memory-hex", "00"],
    ["-memory-bytes", "1", "-memory-hex", "z0"],
    ["-memory-bytes", "1", "-memory-hex", "f"],
    ["-memory-bytes", "1", "-memory-hex", "0000"],
    ["-memory-bytes", "1", "-canonical"],
    ["-memory-bytes", "1", "-profile", ref.PROFILE],
    ["-dump-memory", "-profile", ref.PROFILE],
    ["-max-steps", "-1"],
])
def test_memory_cli_configuration_errors(flags, runner):
    process = subprocess.run([str(runner), "-profile", ref.MEMORY_PROFILE] + flags + ["-"],
                             input="halt", encoding="utf-8", capture_output=True, timeout=10)
    assert process.returncode == 2 and process.stderr and not process.stdout


def test_memory_cli_initial_zero_fill_and_opt_in_output(runner):
    process = subprocess.run([str(runner), "-profile", ref.MEMORY_PROFILE, "-memory-bytes", "4",
                              "-memory-hex", "aa", "-dump-memory", "-"],
                             input="halt", encoding="utf-8", capture_output=True, timeout=10)
    assert process.returncode == 0
    assert json.loads(process.stdout)["memory_hex"] == "aa000000"
    process = invoke(runner, "halt", b"\x00", dump=False)
    assert process.returncode == 0 and "memory_hex" not in json.loads(process.stdout)
    process = invoke(runner, "load8u r1, r0\nhalt", b"", dump=True)
    assert process.returncode == 1
    result = json.loads(process.stdout)
    assert result["code"] == "memory_out_of_bounds" and result["memory_hex"] == ""


def test_reference_does_not_mutate_initial_memory():
    code, _ = ref.parse("const r1, 7\nstore8 r0, r1\nhalt", ref.MEMORY_PROFILE)
    initial = bytearray(b"\xaa")
    first = ref.run_memory(code, 3, initial)
    assert initial == bytearray(b"\xaa") and first["memory_hex"] == "07"
    assert first == ref.run_memory(code, 3, initial)
    with pytest.raises(ValueError):
        ref.run_memory(code, 3, bytes(ref.MAX_MEMORY_BYTES + 1))


def test_registry_extension_is_not_a_copy_of_arithmetic():
    assert not (set(ref.REGISTRY["opcodes"]) & set(ref.MEMORY_EXTENSION["opcodes"]))
    resolved = ref.registry_for_profile(ref.MEMORY_PROFILE)
    assert len(resolved["opcodes"]) == 33
    for name, definition in ref.REGISTRY["opcodes"].items():
        assert resolved["opcodes"][name] == definition
    used = {line.split()[0] for case in CORPUS["valid"] for line in case["source"].splitlines()}
    assert set(ref.MEMORY_EXTENSION["opcodes"]) <= used
