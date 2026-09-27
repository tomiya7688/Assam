"""Core ASSAM intermediate representation and JSON conversion."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import json

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
    def __post_init__(self): self.instructions, self.labels = list(self.instructions), dict(self.labels)
    def to_dict(self): return {"instructions": [x.to_dict() for x in self.instructions], "labels": dict(self.labels)}
    def to_json(self, *, indent=2): return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
    @classmethod
    def from_dict(cls, value):
        items=value.get("instructions", [])
        if not isinstance(items, list): raise ValueError("program instructions must be a list")
        return cls([Instruction.from_dict(x) for x in items], value.get("labels", {}))
    @classmethod
    def from_json(cls, source):
        value=json.loads(source)
        if not isinstance(value, dict): raise ValueError("program JSON must be an object")
        return cls.from_dict(value)