"""Assam命令レジストリ(schema v3)の読込みと一貫性検査。"""

from __future__ import annotations

import json
import re
from pathlib import Path

REGISTRY_PATH = Path(__file__).with_name("data") / "instruction_registry.json"

_OPERAND_KINDS = {
    "register",
    "immediate",
    "symbol",
    "memory_offset",
    "helper_id",
    "trap_code",
    "value",
    "integer",
    "address",
    "name",
    "target",
}
_LEGACY_INTEGER_KINDS = {"register", "value", "integer", "address"}
_ACCESS = {"read", "write", "none"}
_CONTROL = {
    "next",
    "jump",
    "conditional",
    "link",
    "indirect",
    "halt",
    "trap",
    "call",
    "return",
}
_V1_TRAP_KINDS = {
    "div_by_zero",
    "memory_out_of_range",
    "invalid_jump_target",
    "unknown_helper",
    "explicit",
}
_LEGACY_TRAP_KINDS = {
    "division_by_zero",
    "negative_shift_count",
    "call_stack_underflow",
    "data_stack_underflow",
}
_CLASSIFICATIONS = {"ordinary", "abi_primitive"}
_ID = re.compile(r"(core|draft|full)\.[a-z][a-z0-9]*")
_DRAFT_MAPPING_ID = re.compile(r"assam\.core\.draft\.[a-z][a-z0-9_]*")
_V1_MAPPING_ID = re.compile(r"assam\.core\.1\.[a-z][a-z0-9]*")

# 実行方法はレジストリに置かず、命令idからPython側の実装名を引く表で持つ(設計: レジストリとconformance 2.)
_EXECUTION = {
    "draft.move": {"handler": "move"},
    "draft.load": {"handler": "load"},
    "draft.store": {"handler": "store"},
    "draft.add": {"handler": "binary", "operation": "add"},
    "draft.subtract": {"handler": "binary", "operation": "subtract"},
    "draft.multiply": {"handler": "binary", "operation": "multiply"},
    "draft.divide": {"handler": "binary", "operation": "divide"},
    "draft.modulo": {"handler": "binary", "operation": "modulo"},
    "draft.and": {"handler": "binary", "operation": "and"},
    "draft.or": {"handler": "binary", "operation": "or"},
    "draft.xor": {"handler": "binary", "operation": "xor"},
    "draft.not": {"handler": "unary", "operation": "not"},
    "draft.shiftleft": {"handler": "binary", "operation": "shiftleft"},
    "draft.shiftright": {"handler": "binary", "operation": "shiftright"},
    "draft.compare": {"handler": "compare"},
    "draft.jump": {"handler": "jump"},
    "draft.jumpequal": {"handler": "conditional", "predicate": "equal"},
    "draft.jumpnotequal": {"handler": "conditional", "predicate": "not_equal"},
    "draft.call": {"handler": "call"},
    "draft.return": {"handler": "return"},
    "draft.halt": {"handler": "halt"},
    "full.push": {"handler": "push"},
    "full.pop": {"handler": "pop"},
    "full.createterminal": {"handler": "create_terminal"},
    "full.destroyterminal": {"handler": "destroy_terminal"},
    "full.connectterminal": {"handler": "connect_terminal"},
    "full.disconnectterminal": {"handler": "disconnect_terminal"},
    "full.send": {"handler": "send"},
    "full.broadcast": {"handler": "broadcast"},
}


def _fail(message: str) -> RuntimeError:
    return RuntimeError(f"malformed Assam instruction registry: {message}")


def _is_str(value) -> bool:
    return isinstance(value, str) and bool(value)


def _positions(operands: list, access: str) -> tuple[int, ...]:
    return tuple(
        index for index, operand in enumerate(operands) if operand["access"] == access
    )


# {"責務": "レジストリJSONを読み、一貫性を検査して定義表を返す", "処理": ["JSON読込み", "各項目の構造検査", "id・名前・対応表idの重複検査", "旧定義(Draft/Full)とCore v1定義に分類"], "引数": ["path: レジストリJSONのパス"], "戻り値": ["旧定義dict(キーは小文字名)", "名前から正式名への表", "Core v1定義dict(キーはmnemonic)", "レジストリ情報dict"], "副作用": [], "エラー": ["不正な場合にRuntimeError"]}
def load_registry(
    path: Path = REGISTRY_PATH,
) -> tuple[dict[str, dict], dict[str, str], dict[str, dict], dict]:
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load Assam instruction registry: {exc}") from exc
    if not isinstance(registry, dict) or registry.get("schema_version") != 3:
        raise RuntimeError("unsupported Assam instruction registry schema")
    profiles = registry.get("profiles")
    if not isinstance(profiles, dict) or not isinstance(
        registry.get("instructions"), list
    ):
        raise _fail("profiles and instructions are required")

    legacy: dict[str, dict] = {}
    names: dict[str, str] = {}
    core_v1: dict[str, dict] = {}
    ids: set[str] = set()
    mapping_ids: set[str] = set()
    full_names: dict[str, str] = {}
    for item in registry["instructions"]:
        entry = _check_entry(item)
        if entry["id"] in ids:
            raise _fail(f"duplicate id {entry['id']!r}")
        ids.add(entry["id"])
        mapping_id = entry.get("target_mapping_id")
        if mapping_id is not None:
            if mapping_id in mapping_ids:
                raise _fail(f"duplicate target mapping id {mapping_id!r}")
            mapping_ids.add(mapping_id)
        if entry["id"].startswith("core."):
            mnemonic = entry["mnemonic"]
            if mnemonic in core_v1:
                raise _fail(f"duplicate mnemonic {mnemonic!r}")
            core_v1[mnemonic] = entry
            for name in entry.get("full_names", []):
                key = name.lower()
                if key in full_names:
                    raise _fail(f"full_names collision {name!r}")
                full_names[key] = entry["id"]
        else:
            _add_legacy(entry, legacy, names)
    for key in full_names:
        if key in names:
            raise _fail(f"full_names collision with legacy name {key!r}")
    metadata = {"schema_version": 3, "profiles": profiles}
    return legacy, names, core_v1, metadata


# {"責務": "1項目の構造(id・availability・operands・effects・trap・対応表id)を検査する", "処理": ["型と列挙値の検査", "Core v1は命名規則とtrap列挙を検査", "Draftは対応表id、Full専用は対応表idなしを検査"], "引数": ["item: 検査する項目"], "戻り値": ["検査済みの項目"], "副作用": [], "エラー": ["不正な場合にRuntimeError"]}
def _check_entry(item) -> dict:
    if not isinstance(item, dict):
        raise _fail("entries must be objects")
    ident, mnemonic = item.get("id"), item.get("mnemonic")
    aliases = item.get("aliases", [])
    if not _is_str(ident) or _ID.fullmatch(ident) is None or not _is_str(mnemonic):
        raise _fail(f"bad id or mnemonic: {item!r}")
    if not isinstance(aliases, list) or any(not _is_str(alias) for alias in aliases):
        raise _fail(f"bad aliases: {ident}")
    availability = item.get("availability")
    if (
        not isinstance(availability, list)
        or not availability
        or any(
            not isinstance(slot, dict) or slot.get("profile") not in {"core", "full"}
            for slot in availability
        )
    ):
        raise _fail(f"bad availability: {ident}")
    operands = item.get("operands")
    if not isinstance(operands, list) or any(
        not isinstance(operand, dict)
        or not _is_str(operand.get("role"))
        or operand.get("kind") not in _OPERAND_KINDS
        or operand.get("access") not in _ACCESS
        for operand in operands
    ):
        raise _fail(f"bad operands: {ident}")
    effects = item.get("effects")
    memory = effects.get("memory") if isinstance(effects, dict) else None
    if (
        not isinstance(memory, dict)
        or type(memory.get("read")) is not bool
        or type(memory.get("write")) is not bool
        or effects.get("control") not in _CONTROL
    ):
        raise _fail(f"bad effects: {ident}")
    full_names = item.get("full_names", [])
    if not isinstance(full_names, list) or any(
        not _is_str(name) for name in full_names
    ):
        raise _fail(f"bad full_names: {ident}")
    if item.get("classification", "ordinary") not in _CLASSIFICATIONS:
        raise _fail(f"bad classification: {ident}")
    mapping_id = item.get("target_mapping_id")
    if ident.startswith("core."):
        traps = item.get("traps")
        if (
            not isinstance(traps, list)
            or any(trap not in _V1_TRAP_KINDS for trap in traps)
            or _V1_MAPPING_ID.fullmatch(mapping_id or "") is None
            or mapping_id != f"assam.core.1.{mnemonic}"
            or ident != f"core.{mnemonic}"
        ):
            raise _fail(f"bad Core v1 entry: {ident}")
    elif ident.startswith("draft."):
        if _DRAFT_MAPPING_ID.fullmatch(mapping_id or "") is None:
            raise _fail(f"Draft Core entries need a draft target_mapping_id: {ident}")
    elif mapping_id is not None:
        raise _fail(f"Full-only entries must not have target_mapping_id: {ident}")
    return item


def _valid_positions(positions, count: int) -> bool:
    return (
        isinstance(positions, list)
        and all(
            type(position) is int and 0 <= position < count for position in positions
        )
        and len(set(positions)) == len(positions)
    )


# {"責務": "Draft/Full項目を旧来の定義dict形式に変換して登録する", "処理": ["整数parameter位置とtrap条件の検査", "Python側実行表からhandler等を結合", "名前とaliasの重複検査"], "引数": ["entry: 検査済み項目", "legacy: 定義表(更新される)", "names: 名前から正式名への表(更新される)"], "戻り値": [], "副作用": ["legacyとnamesを更新する"], "エラー": ["不正・重複時にRuntimeError"]}
def _add_legacy(entry: dict, legacy: dict, names: dict) -> None:
    ident, operands = entry["id"], entry["operands"]
    integer_operands = entry.get("integer_operands")
    if integer_operands is not None and (
        not _valid_positions(integer_operands, len(operands))
        or any(
            operands[position]["kind"] not in _LEGACY_INTEGER_KINDS
            for position in integer_operands
        )
    ):
        raise _fail(f"bad integer_operands: {ident}")
    has_integer_data = any(
        operand["kind"] in _LEGACY_INTEGER_KINDS for operand in operands
    )
    if ident.startswith("draft.") and has_integer_data and integer_operands is None:
        raise _fail(f"Draft Core entry needs integer_operands: {ident}")
    trap_conditions = entry.get("trap_conditions", [])
    if not isinstance(trap_conditions, list):
        raise _fail(f"bad trap_conditions: {ident}")
    for condition in trap_conditions:
        if (
            not isinstance(condition, dict)
            or set(condition) != {"kind", "operand_positions"}
            or condition["kind"] not in _LEGACY_TRAP_KINDS
            or not _valid_positions(condition["operand_positions"], len(operands))
            or any(
                operands[position]["kind"] not in _LEGACY_INTEGER_KINDS
                for position in condition["operand_positions"]
            )
        ):
            raise _fail(f"bad trap_conditions: {ident}")
    execution = _EXECUTION.get(ident)
    if execution is None:
        raise _fail(f"no Python execution entry for {ident}")
    definition = {
        "opcode": entry["mnemonic"],
        "aliases": tuple(entry.get("aliases", [])),
        "operands": tuple(operand["kind"] for operand in operands),
        "read_operands": _positions(operands, "read"),
        "write_operands": _positions(operands, "write"),
        "data_memory_effects": {
            "read": entry["effects"]["memory"]["read"],
            "write": entry["effects"]["memory"]["write"],
        },
        "flow": entry["effects"]["control"],
        "profile": "core" if ident.startswith("draft.") else "full",
        "canonical_name": entry["mnemonic"],
        "id": ident,
        **execution,
    }
    if integer_operands is not None:
        definition["integer_parameters"] = {
            "operand_positions": list(integer_operands),
            "width": "not_decided",
            "signedness": "not_decided",
        }
    if "target_mapping_id" in entry:
        definition["target_mapping_id"] = entry["target_mapping_id"]
    definition["trap_conditions"] = tuple(
        {"kind": c["kind"], "operand_positions": tuple(c["operand_positions"])}
        for c in trap_conditions
    )
    canonical = entry["mnemonic"].lower()
    if canonical in names:
        raise _fail(f"duplicate instruction name or alias {entry['mnemonic']!r}")
    names[canonical] = canonical
    legacy[canonical] = definition
    for alias in entry.get("aliases", []):
        key = alias.lower()
        if key in names:
            raise _fail(f"duplicate instruction name or alias {alias!r}")
        names[key] = canonical
