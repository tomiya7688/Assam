"""Core ASSAM intermediate representation and JSON conversion."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import json
from .profile import ProgramProfile

@dataclass(frozen=True)
class Instruction:
    opcode: str
    operands: tuple[Any, ...] = ()
    source_line: int | None = None
    def __post_init__(self):
        if not self.opcode or self.opcode != self.opcode.strip(): raise ValueError("opcode must be a non-empty, trimmed string")
    def to_dict(self): return {"opcode": self.opcode, "operands": list(self.operands)}
    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or not isinstance(value.get("opcode"), str): raise ValueError("instruction must contain a string opcode")
        operands=value.get("operands", [])
        if not isinstance(operands, list): raise ValueError("instruction operands must be a list")
        return cls(value["opcode"], tuple(operands))

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
        value = {"instructions": [x.to_dict() for x in self.instructions], "labels": dict(self.labels)}
        if self.profile is not None:
            value["profile"] = self.profile.to_dict()
        return value
    def to_json(self, *, indent=2): return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict): raise ValueError("program must be an object")
        items=value.get("instructions", [])
        if not isinstance(items, list): raise ValueError("program instructions must be a list")
        instructions=[Instruction.from_dict(x) for x in items]
        labels=value.get("labels", {})
        if not isinstance(labels, dict): raise ValueError("labels must be an object")
        for name, target in labels.items():
            if not isinstance(name, str) or not name:
                raise ValueError(f"invalid label name: {name!r}")
            if type(target) is not int:
                raise ValueError(f"label {name!r} target must be an integer")
            if not 0 <= target < len(instructions):
                raise ValueError(f"label {name!r} target out of range: {target}")
        profile = ProgramProfile.from_dict(value["profile"]) if "profile" in value else None
        return cls(instructions, labels, profile)
    @classmethod
    def from_json(cls, source):
        value=json.loads(source)
        if not isinstance(value, dict): raise ValueError("program JSON must be an object")
        return cls.from_dict(value)
