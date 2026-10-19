"""Validate target coverage manifests against the Assam Core registry."""

import json
import re
from pathlib import Path


_TARGET_MAPPING_ID = re.compile(r"^assam\.core\.draft\.[a-z][a-z0-9_]*$")
_DEFAULT_REGISTRY = Path(__file__).parent / "data" / "instruction_registry.json"
_REQUIRED_ARCHITECTURES = ("x64", "arm64", "riscv")
_ARCHITECTURE_ALIASES = {
    "x64": "x64",
    "x86-64": "x64",
    "arm64": "arm64",
    "aarch64": "arm64",
    "riscv": "riscv",
    "risc-v": "riscv",
}


def check_target_coverage(manifest_path, registry_path=None):
    """Return coverage counts or raise ValueError for an inconsistent manifest."""
    manifest = _read_json(Path(manifest_path), "coverage manifest")
    registry_path = Path(registry_path) if registry_path else _DEFAULT_REGISTRY
    registry, core_ids = _load_core_mapping_ids(registry_path)
    return _check_coverage_manifest(manifest, registry, core_ids)


def _check_coverage_manifest(manifest, registry, core_ids):
    _require_object_keys(
        manifest,
        {"schema_version", "core_profile", "registry_schema_version", "target", "coverage"},
        {"schema_version", "core_profile", "registry_schema_version", "target", "coverage"},
        "coverage manifest",
    )
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("coverage manifest schema_version must be 1")
    _require_object_keys(manifest["core_profile"], {"name", "version"}, {"name", "version"}, "core_profile")
    if manifest["core_profile"] != {"name": "Assam Core", "version": "draft"}:
        raise ValueError("coverage manifest core_profile must identify Assam Core draft")
    if type(manifest["registry_schema_version"]) is not int or manifest["registry_schema_version"] != registry["schema_version"]:
        raise ValueError("coverage manifest registry_schema_version does not match the registry")

    target = manifest["target"]
    _require_object_keys(target, {"architecture", "profile"}, {"architecture", "profile"}, "target")
    if any(
        not isinstance(target[key], str) or not target[key].strip()
        for key in ("architecture", "profile")
    ):
        raise ValueError("coverage manifest target must have non-empty architecture and profile")

    entries = manifest["coverage"]
    if not isinstance(entries, list):
        raise ValueError("coverage manifest coverage must be an array")
    seen = set()
    in_scope = 0
    out_of_scope = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("coverage entries must be objects")
        allowed = {"target_mapping_id", "disposition", "reason"}
        required = {"target_mapping_id", "disposition"}
        _require_object_keys(entry, allowed, required, "coverage entry")
        mapping_id = entry["target_mapping_id"]
        if not isinstance(mapping_id, str) or not _TARGET_MAPPING_ID.fullmatch(mapping_id):
            raise ValueError("coverage entry has an invalid target_mapping_id")
        if mapping_id in seen:
            raise ValueError(f"duplicate target_mapping_id in coverage manifest: {mapping_id}")
        seen.add(mapping_id)
        disposition = entry["disposition"]
        if disposition == "in_scope":
            in_scope += 1
        elif disposition == "out_of_scope":
            reason = entry.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(f"out_of_scope entry requires a non-empty reason: {mapping_id}")
            out_of_scope += 1
        else:
            raise ValueError(f"invalid disposition for {mapping_id}: expected in_scope or out_of_scope")

    missing = sorted(set(core_ids) - seen)
    unknown = sorted(seen - set(core_ids))
    if missing or unknown:
        details = []
        if missing:
            details.append("missing Core IDs: " + ", ".join(missing))
        if unknown:
            details.append("unknown IDs: " + ", ".join(unknown))
        raise ValueError("; ".join(details))

    return {
        "validation_scope": "coverage_declarations_only",
        "architecture": target["architecture"],
        "profile": target["profile"],
        "core_total": len(core_ids),
        "in_scope": in_scope,
        "out_of_scope": out_of_scope,
    }


def check_target_mappings(mapping_path, registry_path=None, coverage_path=None):
    """Validate mapping structure and registry references, not ISA semantics."""
    mapping_table = _read_json(Path(mapping_path), "target mapping table")
    registry_path = Path(registry_path) if registry_path else _DEFAULT_REGISTRY
    registry, core_ids = _load_core_mapping_ids(registry_path)

    _require_object_keys(
        mapping_table,
        {"schema_version", "core_profile", "registry_schema_version", "target", "mappings"},
        {"schema_version", "core_profile", "registry_schema_version", "target", "mappings"},
        "target mapping table",
    )
    if type(mapping_table["schema_version"]) is not int or mapping_table["schema_version"] != 1:
        raise ValueError("target mapping schema_version must be 1")
    _require_object_keys(mapping_table["core_profile"], {"name", "version"}, {"name", "version"}, "core_profile")
    if mapping_table["core_profile"] != {"name": "Assam Core", "version": "draft"}:
        raise ValueError("target mapping core_profile must identify Assam Core draft")
    if type(mapping_table["registry_schema_version"]) is not int or mapping_table["registry_schema_version"] != registry["schema_version"]:
        raise ValueError("target mapping registry_schema_version does not match the registry")

    target = mapping_table["target"]
    _require_object_keys(target, {"architecture", "profile"}, {"architecture", "profile"}, "target")
    if any(not isinstance(target[key], str) or not target[key].strip() for key in ("architecture", "profile")):
        raise ValueError("target mapping target must have non-empty architecture and profile")

    mappings = mapping_table["mappings"]
    if not isinstance(mappings, list) or not mappings:
        raise ValueError("target mapping mappings must be a non-empty array")
    core_instructions = {
        instruction["target_mapping_id"]: instruction
        for instruction in registry["instructions"]
        if instruction.get("profile") == "core"
    }
    seen = set()
    instruction_count = 0
    for mapping in mappings:
        _require_object_keys(mapping, {"target_mapping_id", "sequence"}, {"target_mapping_id", "sequence"}, "target mapping entry")
        mapping_id = mapping["target_mapping_id"]
        if not isinstance(mapping_id, str) or not _TARGET_MAPPING_ID.fullmatch(mapping_id):
            raise ValueError("target mapping entry has an invalid target_mapping_id")
        if mapping_id in seen:
            raise ValueError(f"duplicate target_mapping_id in mapping table: {mapping_id}")
        seen.add(mapping_id)
        if mapping_id not in core_instructions:
            raise ValueError(f"unknown Core target_mapping_id value: {mapping_id}")
        core_operands = core_instructions[mapping_id].get("operands")
        if not isinstance(core_operands, list):
            raise ValueError(f"Core registry operands must be an array: {mapping_id}")
        sequence = mapping["sequence"]
        if not isinstance(sequence, list) or not sequence:
            raise ValueError(f"mapping sequence must be a non-empty array: {mapping_id}")
        for instruction in sequence:
            _require_object_keys(instruction, {"opcode", "operands"}, {"opcode", "operands"}, "target instruction")
            if not isinstance(instruction["opcode"], str) or not instruction["opcode"].strip():
                raise ValueError(f"target instruction opcode must be non-empty: {mapping_id}")
            operands = instruction["operands"]
            if not isinstance(operands, list):
                raise ValueError(f"target instruction operands must be an array: {mapping_id}")
            for operand in operands:
                _validate_target_operand(operand, mapping_id, len(core_operands))
            instruction_count += 1

    report = {
        "validation_scope": "mapping_structure_and_registry_references_only",
        "architecture": target["architecture"],
        "profile": target["profile"],
        "mapping_count": len(seen),
        "target_instruction_count": instruction_count,
        "core_ids_without_mapping": sorted(set(core_ids) - seen),
    }
    if coverage_path is not None:
        manifest = _read_json(Path(coverage_path), "coverage manifest")
        coverage_report = _check_coverage_manifest(manifest, registry, core_ids)
        if (
            _canonical_architecture(target["architecture"])
            != _canonical_architecture(coverage_report["architecture"])
            or target["profile"] != coverage_report["profile"]
        ):
            raise ValueError("mapping table and coverage manifest target architecture/profile must match")
        expected_ids = {
            entry["target_mapping_id"]
            for entry in manifest["coverage"]
            if entry["disposition"] == "in_scope"
        }
        missing = sorted(expected_ids - seen)
        excluded = sorted(seen - expected_ids)
        if missing or excluded:
            details = []
            if missing:
                details.append("missing in_scope mappings: " + ", ".join(missing))
            if excluded:
                details.append("mappings declared out_of_scope: " + ", ".join(excluded))
            raise ValueError("; ".join(details))
        report["validation_scope"] = "mapping_structure_registry_references_and_coverage_only"
        report["coverage"] = coverage_report
    return report


def _validate_target_operand(operand, mapping_id, core_operand_count):
    if not isinstance(operand, dict) or not isinstance(operand.get("kind"), str):
        raise ValueError(f"invalid target operand template: {mapping_id}")
    kind = operand["kind"]
    if kind == "core_operand":
        _require_object_keys(operand, {"kind", "index"}, {"kind", "index"}, "core_operand template")
        if type(operand["index"]) is not int or operand["index"] < 0:
            raise ValueError(f"core_operand index must be a non-negative integer: {mapping_id}")
        if operand["index"] >= core_operand_count:
            raise ValueError(
                f"core_operand index {operand['index']} is out of range for "
                f"{mapping_id}: Core instruction has {core_operand_count} operand(s)"
            )
    elif kind == "immediate":
        _require_object_keys(operand, {"kind", "value"}, {"kind", "value"}, "immediate template")
        if type(operand["value"]) is not int:
            raise ValueError(f"immediate value must be an integer: {mapping_id}")
    elif kind in {"target_register", "scratch", "symbol"}:
        _require_object_keys(operand, {"kind", "name"}, {"kind", "name"}, f"{kind} template")
        if not isinstance(operand["name"], str) or not operand["name"].strip():
            raise ValueError(f"{kind} name must be non-empty: {mapping_id}")
    else:
        raise ValueError(f"unsupported target operand template kind {kind!r}: {mapping_id}")


def build_target_coverage_template(architecture, profile, registry_path=None):
    """Build a manifest with every Core ID explicitly pending/out of scope."""
    if not isinstance(architecture, str) or not architecture.strip():
        raise ValueError("target architecture must be a non-empty string")
    if not isinstance(profile, str) or not profile.strip():
        raise ValueError("target profile must be a non-empty string")
    registry_path = Path(registry_path) if registry_path else _DEFAULT_REGISTRY
    registry, core_ids = _load_core_mapping_ids(registry_path)
    return {
        "schema_version": 1,
        "core_profile": registry["core_profile"],
        "registry_schema_version": registry["schema_version"],
        "target": {"architecture": architecture.strip(), "profile": profile.strip()},
        "coverage": [
            {
                "target_mapping_id": mapping_id,
                "disposition": "out_of_scope",
                "reason": "No target instruction mapping is specified yet; review this entry before use.",
            }
            for mapping_id in core_ids
        ],
    }


def check_target_matrix(manifest_paths, registry_path=None):
    """Check per-manifest completeness and declaration of each required architecture."""
    reports = [check_target_coverage(path, registry_path) for path in manifest_paths]
    if not reports:
        raise ValueError("at least one target coverage manifest is required")

    architectures = set()
    profiles = set()
    for report in reports:
        architecture = _canonical_architecture(report["architecture"])
        profile = report["profile"]
        identity = (architecture, profile)
        if identity in profiles:
            raise ValueError(f"duplicate target coverage manifest for {architecture}/{profile}")
        profiles.add(identity)
        architectures.add(architecture)

    missing = sorted(set(_REQUIRED_ARCHITECTURES) - architectures)
    if missing:
        raise ValueError("missing required target architecture declarations: " + ", ".join(missing))
    return {
        "validation_scope": "coverage_declarations_only",
        "manifest_count": len(reports),
        "architectures": sorted(architectures),
    }


def _canonical_architecture(architecture):
    normalized = architecture.strip().lower().replace("_", "-")
    return _ARCHITECTURE_ALIASES.get(normalized, normalized)


def _require_object_keys(value, allowed, required, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    missing = required - value.keys()
    extra = value.keys() - allowed
    if missing or extra:
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if extra:
            details.append("unknown " + ", ".join(sorted(extra)))
        raise ValueError(f"{label}: " + "; ".join(details))


def _load_core_mapping_ids(registry_path):
    registry = _read_json(registry_path, "instruction registry")
    if not isinstance(registry, dict) or type(registry.get("schema_version")) is not int or registry["schema_version"] != 2:
        raise ValueError("instruction registry schema_version must be 2")
    if registry.get("core_profile") != {"name": "Assam Core", "version": "draft"}:
        raise ValueError("instruction registry core_profile must identify Assam Core draft")
    instructions = registry.get("instructions")
    if not isinstance(instructions, list):
        raise ValueError("instruction registry instructions must be an array")
    core_ids = []
    for instruction in instructions:
        if not isinstance(instruction, dict):
            raise ValueError("instruction registry entries must be objects")
        if instruction.get("profile") != "core":
            continue
        mapping_id = instruction.get("target_mapping_id")
        if not isinstance(mapping_id, str) or not _TARGET_MAPPING_ID.fullmatch(mapping_id):
            raise ValueError(f"Core instruction {instruction.get('opcode', '<unknown>')} has an invalid target_mapping_id")
        core_ids.append(mapping_id)
    if not core_ids:
        raise ValueError("instruction registry must define at least one Core target_mapping_id")
    if len(core_ids) != len(set(core_ids)):
        raise ValueError("instruction registry contains duplicate Core target_mapping_id values")
    return registry, core_ids


def _read_json(path, label):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {path}: {exc}") from exc
