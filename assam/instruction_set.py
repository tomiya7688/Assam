"""Load the versioned canonical Assam instruction registry."""

from __future__ import annotations

import re

from .instruction_registry import load_registry
from .ir import Immediate, Program, Register, StringLiteral, Symbol
from .profile import ProgramProfile

DEFAULT_REGISTER_COUNT = 32  # r0..r31 in both Full and Core (WP-B1)


class InstructionSet:
    """Single source for instruction syntax, execution metadata, and effects."""

    # Draft/Fullの定義(VM・analyzer・parserが使う)とCore v1の定義を別々に持つ
    _definitions, _names, _core_v1, _registry = load_registry()

    def __init__(self, register_count: int = DEFAULT_REGISTER_COUNT) -> None:
        if type(register_count) is not int or register_count < 1:
            raise ValueError("register_count must be positive")
        self.register_count = register_count

    def canonical_opcode(self, opcode: str) -> str | None:
        return self._names.get(opcode.lower())

    def definition(self, opcode: str) -> dict | None:
        canonical = self.canonical_opcode(opcode)
        return self._definitions.get(canonical) if canonical is not None else None

    def definitions(self) -> dict[str, dict]:
        return {
            name: definition.copy() for name, definition in self._definitions.items()
        }

    # {"責務": "Core v1命令の定義表を返す", "処理": ["各定義をコピーして返す"], "引数": [], "戻り値": ["mnemonicから定義への辞書"], "副作用": [], "エラー": []}
    def core_v1_definitions(self) -> dict[str, dict]:
        """Core v1命令の定義(mnemonic→項目)。parser/VMはB2/B4で使う。"""
        return {name: definition.copy() for name, definition in self._core_v1.items()}

    @classmethod
    def registry_metadata(cls) -> dict:
        return cls._registry.copy()

    @classmethod
    # {"責務": "Draft Coreのprofile印を返す", "処理": ["固定値を返す"], "引数": [], "戻り値": ["ProgramProfile(Assam Core, draft, 2)"], "副作用": [], "エラー": []}
    def core_profile_marker(cls) -> ProgramProfile:
        # Draft Coreの印。IRにはレジストリv2時代の印(registry_schema_version=2)が付く。
        # v1の印(version "1", registry_schema_version 3)はB2で導入し、Draftは廃止予定(Q4)。
        return ProgramProfile("Assam Core", "draft", 2)

    @classmethod
    # {"責務": "Core v1のprofile印を返す", "処理": ["固定値を返す"], "引数": [], "戻り値": ["ProgramProfile(Assam Core, 1, 3)"], "副作用": [], "エラー": []}
    def core_v1_profile_marker(cls) -> ProgramProfile:
        return ProgramProfile("Assam Core", "1", 3)

    def resolve_profile(self, program: Program, requested: str | None = None) -> str:
        if requested is not None and requested not in {"core", "full"}:
            raise ValueError(f"unknown ASSAM profile: {requested!r}")
        declared = None
        if program.profile is not None:
            if program.profile != self.core_profile_marker():
                raise ValueError(
                    f"unsupported or incompatible program profile: {program.profile!r}"
                )
            declared = "core"
        if declared is not None and requested is not None and declared != requested:
            raise ValueError(
                f"program declares profile {declared!r}, not requested profile {requested!r}"
            )
        return requested or declared or "full"

    def validate(self, program: Program, *, profile: str | None = None) -> None:
        """Raise ValueError with instruction context if a program is invalid."""
        profile = self.resolve_profile(program, profile)
        instruction_count = len(program.instructions)
        for label, index in program.labels.items():
            if not isinstance(label, str) or not label:
                raise ValueError(f"invalid label name: {label!r}")
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or not 0 <= index < instruction_count
            ):
                raise ValueError(
                    f"label {label!r} points outside the program: {index!r}"
                )

        for index, instruction in enumerate(program.instructions):
            definition = self.definition(instruction.opcode)
            if definition is None:
                self._fail(index, instruction, f"unknown opcode {instruction.opcode!r}")
            if profile == "core" and definition["profile"] != "core":
                self._fail(
                    index, instruction, "instruction is outside the Assam Core profile"
                )
            expected = definition["operands"]
            if len(instruction.operands) != len(expected):
                self._fail(
                    index,
                    instruction,
                    f"expected {len(expected)} operands, got {len(instruction.operands)}",
                )
            for position, (role, operand) in enumerate(
                zip(expected, instruction.operands), 1
            ):
                if profile == "core" and self._core_forbidden(role, operand):
                    self._fail(
                        index,
                        instruction,
                        f"operand {position} ({operand}) is outside the Assam Core profile",
                    )
                if not self._valid_operand(role, operand, program):
                    self._fail(
                        index,
                        instruction,
                        f"operand {position} must be {role}, got {operand!r}",
                    )

    @staticmethod
    def _core_forbidden(role: str, operand) -> bool:
        """Core has no string literals; a bare word is a symbol, so only name/target roles accept it."""
        if isinstance(operand, StringLiteral):
            return True
        return isinstance(operand, Symbol) and role not in {"name", "target"}

    def _valid_operand(self, role: str, value, program: Program) -> bool:
        is_register = isinstance(value, Register)
        valid_register = is_register and value.index < self.register_count
        if role == "register":
            return valid_register
        if role in {"integer", "address"}:
            return isinstance(value, Immediate) or valid_register
        if role == "value":
            if isinstance(value, (Immediate, StringLiteral, Symbol)):
                return True
            return valid_register
        if role == "name":
            if isinstance(value, (Symbol, StringLiteral)):
                return True
            return valid_register
        if role == "target":
            if isinstance(value, Symbol):
                return value.name in program.labels
            return isinstance(value, Immediate) and 0 <= value.value < len(
                program.instructions
            )
        return False

    @staticmethod
    def _fail(index: int, instruction, reason: str) -> None:
        source = (
            f"line {instruction.source_line}, "
            if instruction.source_line is not None
            else ""
        )
        raise ValueError(
            f"{source}instruction {index} ({instruction.opcode}): {reason}"
        )
