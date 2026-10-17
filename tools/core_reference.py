"""Test-only Python oracle for the draft Go bootstrap subset.

Uses the exact same checked-in registry, not a second opcode/operand table.
This does not change the existing Full ASSAM VM or its public Python API.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "core/registry.json").read_text(encoding="utf-8"))
PROFILE = REGISTRY["profile"]
MASK = (1 << 64) - 1
MAX_SOURCE_BYTES = 1 << 20
LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
REGISTER = re.compile(r"r(0|[1-9]|[12][0-9]|3[01])\Z")
IMMEDIATE = re.compile(r"-?(0x[0-9a-fA-F]+|[0-9]+)\Z")


def immediate(text):
    if not IMMEDIATE.fullmatch(text):
        raise ValueError("invalid integer immediate")
    negative = text.startswith("-")
    digits = text.removeprefix("-")
    base = 16 if digits.startswith("0x") else 10
    if base == 16:
        digits = digits[2:]
    digits = digits.lstrip("0") or "0"
    if len(digits) > (16 if base == 16 else 20):
        raise ValueError("integer immediate out of range")
    value = int(digits, base)
    if value > ((1 << 63) if negative else MASK):
        raise ValueError("integer immediate out of range")
    return (-value if negative else value) & MASK


def parse(source, profile):
    if profile != PROFILE:
        raise ValueError("unsupported profile")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES or "\x00" in source:
        raise ValueError("invalid source encoding or source too large")
    code, labels, pending, canonical = [], {}, [], []
    for line, raw in enumerate(source.split("\n"), 1):
        text = raw.split(";", 1)[0].strip(" \t\r")
        if not text:
            continue
        if text.endswith(":"):
            name = text[:-1]
            if not LABEL.fullmatch(name) or name in labels:
                raise ValueError(f"line {line}: invalid/duplicate label")
            labels[name] = len(code)
            canonical.append(name + ":")
            continue
        parts = re.split(r"[ \t]", text, maxsplit=1)
        name = parts[0]
        definition = REGISTRY["opcodes"].get(name)
        if definition is None:
            raise ValueError(f"line {line}: unknown or non-canonical opcode")
        tail = parts[1].strip(" \t") if len(parts) == 2 else ""
        tokens = [a.strip(" \t") for a in tail.split(",")] if tail else []
        if len(tokens) != len(definition["operands"]):
            raise ValueError(f"line {line}: invalid operand count")
        args = []
        for i, (token, kind) in enumerate(zip(tokens, definition["operands"])):
            if kind in ("read_reg", "write_reg"):
                if not REGISTER.fullmatch(token):
                    raise ValueError(f"line {line}: invalid register")
                args.append(int(token[1:]))
            elif kind == "immediate":
                args.append(immediate(token))
                tokens[i] = str(args[-1])
            elif kind == "label":
                if not LABEL.fullmatch(token):
                    raise ValueError(f"line {line}: invalid label")
                pending.append((len(code), i, token))
                args.append(0)
            else:
                raise ValueError("unsupported registry operand")
        code.append((definition["effect"], args, line))
        canonical.append(name + (" " + ", ".join(tokens) if tokens else ""))
    if not code:
        raise ValueError("empty program")
    if any(target >= len(code) for target in labels.values()):
        raise ValueError("label targets end of program")
    for index, operand, name in pending:
        if name not in labels:
            raise ValueError("unresolved label")
        code[index][1][operand] = labels[name]
    canonical_text = "\n".join(canonical) + "\n"
    if len(canonical_text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("canonical source too large")
    return code, canonical_text


def signed(value):
    return value - (1 << 64) if value >= (1 << 63) else value


def run(code, budget):
    if type(budget) is not int or not 0 <= budget <= MASK:
        raise ValueError("budget must be uint64")
    regs = [0] * 32
    pc = steps = 0

    def snapshot(status, code="", line=0):
        return dict(status=status, pc=pc, steps=steps, code=code, line=line,
                    registers=[f"0x{x:016x}" for x in regs])

    if not code:
        return snapshot("invalid_program")
    while True:
        if steps >= budget:
            return snapshot("step_limit")
        if not 0 <= pc < len(code):
            return snapshot("trap", "invalid_pc")
        effect, args, line = code[pc]
        steps += 1
        next_pc, value = pc + 1, None
        if effect == "constant":
            value = args[1]
        elif effect in ("branch_zero", "branch_nonzero"):
            take = regs[args[0]] == 0
            if effect == "branch_nonzero":
                take = not take
            if take:
                next_pc = args[1]
        elif effect == "jump":
            next_pc = args[0]
        elif effect == "halt":
            return snapshot("halted", line=line)
        elif effect == "trap":
            return snapshot("trap", f"explicit:0x{args[0]:016x}", line)
        else:
            x, y = regs[args[1]], regs[args[2]]
            if effect == "add": value = x + y
            elif effect == "sub": value = x - y
            elif effect == "mul": value = x * y
            elif effect == "and": value = x & y
            elif effect == "or": value = x | y
            elif effect == "xor": value = x ^ y
            elif effect == "shl": value = x << (y & 63)
            elif effect == "shr": value = x >> (y & 63)
            elif effect == "sar": value = signed(x) >> (y & 63)
            elif effect == "eq": value = int(x == y)
            elif effect == "ltu": value = int(x < y)
            elif effect == "lts": value = int(signed(x) < signed(y))
            elif effect in ("divu", "divs", "remu", "rems"):
                if y == 0:
                    return snapshot("trap", "division_by_zero", line)
                if effect == "divu": value = x // y
                elif effect == "remu": value = x % y
                else:
                    sx, sy = signed(x), signed(y)
                    quotient = abs(sx) // abs(sy)
                    if (sx < 0) != (sy < 0):
                        quotient = -quotient
                    value = quotient if effect == "divs" else sx - quotient * sy
            else:
                raise ValueError(f"unsupported registry effect: {effect}")
        if value is not None and args[0] != 0:
            regs[args[0]] = value & MASK
        pc = next_pc
