"""Load the versioned canonical Assam instruction registry."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .ir import Program
from .profile import ProgramProfile


_REGISTRY_PATH = Path(__file__).with_name("data") / "instruction_registry.json"
_OPERAND_ROLES = {"register", "value", "integer", "address", "name", "target"}
_FLOW_KINDS = {"next", "jump", "conditional", "call", "return", "halt"}
_TRAP_KINDS = {"division_by_zero", "negative_shift_count", "call_stack_underflow", "data_stack_underflow"}
_TARGET_MAPPING_ID = re.compile(r"assam\.core\.draft\.[a-z][a-z0-9_]*")


def _valid_positions(positions, operand_count: int) -> bool:
    return (
        isinstance(positions, list)
        and all(type(position) is int and 0 <= position < operand_count for position in positions)
        and len(set(positions)) == len(positions)
    )


def _valid_trap_conditions(conditions, operands: list) -> bool:
    if not isinstance(conditions, list):
        return False
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) != {"kind", "operand_positions"}:
            return False
        positions = condition.get("operand_positions")
        if (
            not isinstance(condition.get("kind"), str)
            or condition.get("kind") not in _TRAP_KINDS
            or not _valid_positions(positions, len(operands))
            or any(operands[position] not in {"register", "value", "integer", "address"} for position in positions)
        ):
            return False
    return True


def _load_definitions() -> tuple[dict[str, dict], dict[str, str]]:
    try:
        registry = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load Assam instruction registry: {exc}") from exc
    if not isinstance(registry, dict) or registry.get("schema_version") != 2:
        raise RuntimeError("unsupported Assam instruction registry schema")
    if not isinstance(registry.get("core_profile"), dict) or not isinstance(registry.get("instructions"), list):
        raise RuntimeError("malformed Assam instruction registry")

    definitions = {}
    names = {}
    mapping_ids = set()
    for item in registry["instructions"]:
        if not isinstance(item, dict):
            raise RuntimeError("instruction registry entries must be objects")
        name = item.get("opcode")
        operands = item.get("operands")
        aliases = item.get("aliases", [])
        reads = item.get("read_operands")
        writes = item.get("write_operands")
        memory_effects = item.get("data_memory_effects")
        integer_parameters = item.get("integer_parameters")
        trap_conditions = item.get("trap_conditions", [])
        mapping_id = item.get("target_mapping_id")
        has_integer_data = (
            isinstance(operands, list)
            and any(isinstance(role, str) and role in {"register", "value", "integer", "address"} for role in operands)
        )
        valid_integer_parameters = (
            isinstance(operands, list)
            and isinstance(integer_parameters, dict)
            and set(integer_parameters) == {"operand_positions", "width", "signedness"}
            and _valid_positions(integer_parameters.get("operand_positions"), len(operands))
            and integer_parameters.get("width") == "not_decided"
            and integer_parameters.get("signedness") == "not_decided"
        )
        if valid_integer_parameters:
            valid_integer_parameters = all(
                isinstance(operands[position], str)
                and operands[position] in {"register", "value", "integer", "address"}
                for position in integer_parameters["operand_positions"]
            )
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(operands, list)
            or any(not isinstance(role, str) or role not in _OPERAND_ROLES for role in operands)
            or not isinstance(aliases, list)
            or any(not isinstance(alias, str) or not alias for alias in aliases)
            or not _valid_positions(reads, len(operands))
            or not _valid_positions(writes, len(operands))
            or not isinstance(memory_effects, dict)
            or set(memory_effects) != {"read", "write"}
            or any(type(effect) is not bool for effect in memory_effects.values())
            or (item.get("profile") == "core" and has_integer_data and not valid_integer_parameters)
            or (integer_parameters is not None and not valid_integer_parameters)
            or not isinstance(operands, list)
            or not _valid_trap_conditions(trap_conditions, operands)
            or (item.get("profile") == "core" and (not isinstance(mapping_id, str) or _TARGET_MAPPING_ID.fullmatch(mapping_id) is None))
            or (item.get("profile") == "full" and mapping_id is not None)
            or not isinstance(item.get("handler"), str)
            or item.get("flow") not in _FLOW_KINDS
            or item.get("profile") not in {"core", "full"}
        ):
            raise RuntimeError(f"malformed instruction definition: {item!r}")
        if mapping_id is not None:
            if mapping_id in mapping_ids:
                raise RuntimeError(f"duplicate target mapping id: {mapping_id!r}")
            mapping_ids.add(mapping_id)
        definition = {
            **item,
            "canonical_name": name,
            "operands": tuple(operands),
            "aliases": tuple(aliases),
            "read_operands": tuple(reads),
            "write_operands": tuple(writes),
            "data_memory_effects": memory_effects.copy(),
            "integer_parameters": integer_parameters.copy() if integer_parameters is not None else None,
            "trap_conditions": tuple(
                {"kind": condition["kind"], "operand_positions": tuple(condition["operand_positions"])}
                for condition in trap_conditions
            ),
        }
        canonical = name.lower()
        if canonical in names:
            raise RuntimeError(f"duplicate instruction name or alias: {name!r}")
        names[canonical] = canonical
        definitions[canonical] = definition
        for alias in aliases:
            key = alias.lower()
            if key in names:
                raise RuntimeError(f"duplicate instruction name or alias: {alias!r}")
            names[key] = canonical

    # Keep the registry metadata next to the definitions for callers that need
    # to report which draft profile the loaded instruction set represents.
    definitions["__registry__"] = {
        "schema_version": registry["schema_version"],
        "core_profile": registry["core_profile"].copy(),
    }
    return definitions, names


class InstructionSet:
    """Single source for instruction syntax, execution metadata, and effects."""

    _definitions, _names = _load_definitions()

    def __init__(self, register_count: int = 16) -> None:
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
            name: definition.copy()
            for name, definition in self._definitions.items()
            if not name.startswith("__")
        }

    @classmethod
    def registry_metadata(cls) -> dict:
        return cls._definitions["__registry__"].copy()

    @classmethod
    def core_profile_marker(cls) -> ProgramProfile:
        metadata = cls.registry_metadata()
        definition = metadata["core_profile"]
        return ProgramProfile(definition["name"], definition["version"], metadata["schema_version"])

    def resolve_profile(self, program: Program, requested: str | None = None) -> str:
        if requested is not None and requested not in {"core", "full"}:
            raise ValueError(f"unknown ASSAM profile: {requested!r}")
        declared = None
        if program.profile is not None:
            if program.profile != self.core_profile_marker():
                raise ValueError(f"unsupported or incompatible program profile: {program.profile!r}")
            declared = "core"
        if declared is not None and requested is not None and declared != requested:
            raise ValueError(f"program declares profile {declared!r}, not requested profile {requested!r}")
        return requested or declared or "full"

    def validate(self, program: Program, *, profile: str | None = None) -> None:
        """Raise ValueError with instruction context if a program is invalid."""
        profile = self.resolve_profile(program, profile)
        instruction_count = len(program.instructions)
        for label, index in program.labels.items():
            if not isinstance(label, str) or not label:
                raise ValueError(f"invalid label name: {label!r}")
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < instruction_count:
                raise ValueError(f"label {label!r} points outside the program: {index!r}")

        for index, instruction in enumerate(program.instructions):
            definition = self.definition(instruction.opcode)
            if definition is None:
                self._fail(index, instruction, f"unknown opcode {instruction.opcode!r}")
            if profile == "core" and definition["profile"] != "core":
                self._fail(index, instruction, "instruction is outside the Assam Core profile")
            expected = definition["operands"]
            if len(instruction.operands) != len(expected):
                self._fail(index, instruction, f"expected {len(expected)} operands, got {len(instruction.operands)}")
            for position, (role, operand) in enumerate(zip(expected, instruction.operands), 1):
                if not self._valid_operand(role, operand, program):
                    self._fail(index, instruction, f"operand {position} must be {role}, got {operand!r}")

    def _valid_operand(self, role: str, value, program: Program) -> bool:
        is_register = isinstance(value, str) and re.fullmatch(r"r\d+", value) is not None
        valid_register = is_register and int(value[1:]) < self.register_count
        if role == "register":
            return valid_register
        if role == "integer":
            return type(value) is int or valid_register
        if role == "value":
            return type(value) in {int, str} and (not is_register or valid_register)
        if role == "address":
            return type(value) is int or valid_register
        if role == "name":
            return isinstance(value, str) and bool(value) and (not is_register or valid_register)
        if role == "target":
            if isinstance(value, str):
                return value in program.labels
            return type(value) is int and 0 <= value < len(program.instructions)
        return False

    @staticmethod
    def _fail(index: int, instruction, reason: str) -> None:
        source = f"line {instruction.source_line}, " if instruction.source_line is not None else ""
        raise ValueError(f"{source}instruction {index} ({instruction.opcode}): {reason}")
