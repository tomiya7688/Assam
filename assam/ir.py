"""Core ASSAM intermediate representation and JSON conversion.

Operands are typed (WP-B1, issue #10): a register, an integer immediate, a
symbol (label or helper name) or a string literal. The kind is never inferred
from the content of a string at execution time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union
import json
import re

from .profile import ProgramProfile

IR_SCHEMA_VERSION = 2
_REGISTER_RE = re.compile(r"r(0|[1-9][0-9]*)")
_SYMBOL_RE = re.compile(r"[^\s,;#\"]+")


@dataclass(frozen=True)
class Register:
    """A register reference such as ``r5``."""

    index: int

    def __post_init__(self):
        if type(self.index) is not int or self.index < 0:
            raise ValueError("register index must be a non-negative integer")

    @property
    def name(self) -> str:
        return f"r{self.index}"

    def to_dict(self) -> dict:
        return {"kind": "register", "index": self.index}

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Immediate:
    """A signed integer literal."""

    value: int

    def __post_init__(self):
        if type(self.value) is not int:
            raise ValueError("immediate value must be an integer")

    def to_dict(self) -> dict:
        return {"kind": "immediate", "value": self.value}

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class Symbol:
    """A label reference or a helper/terminal name written as a bare word."""

    name: str

    def __post_init__(self):
        if (
            not isinstance(self.name, str)
            or _SYMBOL_RE.fullmatch(self.name) is None
            or self.name.endswith(":")
        ):
            raise ValueError(f"invalid symbol name: {self.name!r}")
        if _REGISTER_RE.fullmatch(self.name) is not None:
            raise ValueError(f"symbol name looks like a register: {self.name!r}")

    def to_dict(self) -> dict:
        return {"kind": "symbol", "name": self.name}

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class StringLiteral:
    """A quoted string. Its content is data and is never reinterpreted."""

    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise ValueError("string literal value must be a string")

    def to_dict(self) -> dict:
        return {"kind": "string", "value": self.value}

    def __str__(self) -> str:
        out = []
        for ch in self.value:
            if ch == '"':
                out.append('\\"')
            elif ch == "\\":
                out.append("\\\\")
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\t":
                out.append("\\t")
            elif ch == "\r":
                out.append("\\r")
            elif ord(ch) < 0x20 or ord(ch) == 0x7F:
                out.append(f"\\x{ord(ch):02x}")
            else:
                out.append(ch)
        return '"' + "".join(out) + '"'


Operand = Union[Register, Immediate, Symbol, StringLiteral]
_OPERAND_TYPES = (Register, Immediate, Symbol, StringLiteral)


def coerce_operand(value: Any) -> Operand:
    """Convert a Python or v1 IR value into a typed operand.

    An ``int`` becomes an immediate; a register-looking string becomes a
    register; a string that reads back as an integer (it must have been quoted)
    and any string that is not a bare word become a string literal; the
    remaining bare words become symbols.
    """
    if isinstance(value, _OPERAND_TYPES):
        return value
    if type(value) is int:
        return Immediate(value)
    if isinstance(value, str):
        if _REGISTER_RE.fullmatch(value):
            return Register(int(value[1:]))
        try:
            int(value, 0)
        except ValueError:
            pass
        else:
            return StringLiteral(value)
        if _SYMBOL_RE.fullmatch(value) and not value.endswith(":"):
            return Symbol(value)
        return StringLiteral(value)
    raise ValueError(f"unsupported operand value: {value!r}")


_OPERAND_KEYS = {
    "register": {"kind", "index"},
    "immediate": {"kind", "value"},
    "symbol": {"kind", "name"},
    "string": {"kind", "value"},
}


def operand_from_dict(value: Any) -> Operand:
    """Read one tagged (schema v2) operand object.

    Only the keys of the declared kind are accepted; any extra key is rejected
    so that malformed input never loads silently.
    """
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise ValueError("operand must be an object with a string kind")
    kind = value["kind"]
    if kind not in _OPERAND_KEYS:
        raise ValueError(f"unknown operand kind: {kind!r}")
    extra = set(value) - _OPERAND_KEYS[kind]
    if extra:
        raise ValueError(f"unexpected keys for {kind} operand: {sorted(extra)}")
    if kind == "register":
        return Register(value.get("index"))
    if kind == "immediate":
        return Immediate(value.get("value"))
    if kind == "symbol":
        return Symbol(value.get("name"))
    return StringLiteral(value.get("value"))


@dataclass(frozen=True)
class Instruction:
    opcode: str
    operands: tuple[Operand, ...] = ()
    source_line: int | None = None

    def __post_init__(self):
        if not self.opcode or self.opcode != self.opcode.strip():
            raise ValueError("opcode must be a non-empty, trimmed string")
        object.__setattr__(
            self, "operands", tuple(coerce_operand(x) for x in self.operands)
        )

    def to_dict(self):
        return {"opcode": self.opcode, "operands": [x.to_dict() for x in self.operands]}

    @classmethod
    def from_dict(cls, value, *, schema_version: int = IR_SCHEMA_VERSION):
        if not isinstance(value, dict) or not isinstance(value.get("opcode"), str):
            raise ValueError("instruction must contain a string opcode")
        operands = value.get("operands", [])
        if not isinstance(operands, list):
            raise ValueError("instruction operands must be a list")
        if schema_version == 1:
            typed = [coerce_operand(x) for x in operands]
        else:
            typed = [operand_from_dict(x) for x in operands]
        return cls(value["opcode"], tuple(typed))


@dataclass
class Program:
    instructions: list[Instruction] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)
    profile: ProgramProfile | None = None

    def __post_init__(self):
        self.instructions, self.labels = list(self.instructions), dict(self.labels)
        if self.profile is not None and not isinstance(self.profile, ProgramProfile):
            raise ValueError("profile must be a ProgramProfile")

    def to_dict(self):
        value = {
            "schema_version": IR_SCHEMA_VERSION,
            "instructions": [x.to_dict() for x in self.instructions],
            "labels": dict(self.labels),
        }
        if self.profile is not None:
            value["profile"] = self.profile.to_dict()
        return value

    def to_json(self, *, indent=2):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError("program must be an object")
        schema_version = value.get("schema_version", 1)
        if type(schema_version) is not int or schema_version not in (
            1,
            IR_SCHEMA_VERSION,
        ):
            raise ValueError(f"unsupported IR schema_version: {schema_version!r}")
        items = value.get("instructions", [])
        if not isinstance(items, list):
            raise ValueError("program instructions must be a list")
        instructions = [
            Instruction.from_dict(x, schema_version=schema_version) for x in items
        ]
        labels = value.get("labels", {})
        if not isinstance(labels, dict):
            raise ValueError("labels must be an object")
        for name, target in labels.items():
            if not isinstance(name, str) or not name:
                raise ValueError(f"invalid label name: {name!r}")
            if type(target) is not int:
                raise ValueError(f"label {name!r} target must be an integer")
            if not 0 <= target < len(instructions):
                raise ValueError(f"label {name!r} target out of range: {target}")
        profile = (
            ProgramProfile.from_dict(value["profile"]) if "profile" in value else None
        )
        return cls(instructions, labels, profile)

    @classmethod
    def from_json(cls, source):
        value = json.loads(source)
        if not isinstance(value, dict):
            raise ValueError("program JSON must be an object")
        return cls.from_dict(value)
