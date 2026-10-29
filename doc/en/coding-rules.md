# ASSAM Coding Rules

Language: [日本語](../jp/コーディングルール.md) | English

Every contributor, human or AI agent (Claude Code, Codex, ChatGPT, Copilot), must follow these rules. Violations are fixed during PR self-review, before merge.

## Structure

- One class per file.
- Each class has one responsibility.
- Treat a feature and its tests as one focused unit.
- One PR covers one feature (or one documentation change). Do not mix in unrelated formatting or renames.

## Python

- Supported versions follow `requires-python` in `pyproject.toml` (3.10+). Do not rely on newer syntax or standard-library features.
- New modules start with `from __future__ import annotations` and a one-line module docstring.
- Add no external dependencies (standard library only; pytest for tests).
- Fail explicitly on invalid input: `ValueError` for validation, `VMError` for VM runtime. No silent correction or approximation.
- `assam/data/instruction_registry.json` is the single source of truth for instruction specs (operands, effects, traps, mapping IDs); do not duplicate it in code.
- When changing JSON data, keep the matching `assam/data/*.schema.json` consistent.

## Tests

- Add tests for every changed behavior. For bug fixes, write the reproducing test first.
- Tests for `assam/<name>.py` live in `tests/test_<topic>.py`.
- Tests are deterministic (no dependence on time, randomness, network, or host-specific paths).
- Do not report unverified items as complete. The target-mapping checkers verify structure, references, and coverage only, not semantic equivalence.

## Documentation

- Japanese is canonical. Update the English version in the same change. Unresolved decisions stay marked undecided in both languages.
- Update the specification, README, and roadmap in the same PR as any behavior change.
- Check off or remove completed roadmap items.

## Git

- Commit per feature. Messages: imperative one-line summary, plus body when needed.
- Never commit secrets, credentials, build output, or `__pycache__`.
- Do not sweep in or overwrite other contributors' uncommitted or unrelated changes without checking.

## No second inheritance step from a concrete class (mandatory)

- **If class `B` inherits from a concrete class `A`, no class `C` may inherit from `B`** (`A → B → C` is forbidden), including when `B` is abstract.
- One direct inheritance step (`A → B`) is not prohibited by this policy alone. Keep any existing stricter project restriction, such as a ban on inheriting concrete classes at all.
- Do not count implicit language root types such as `Object`, `System.Object`, `java.lang.Object`, or interface implementation/extension.
- Exceptions require explicit project architecture documentation identifying the intentional hierarchy and scope. Existing accidental code is not evidence of an exemption. Compiler/analyzer input examples and test fixtures are distinct from production implementation policy.
- Prefer composition, delegation, or an abstract contract instead of the prohibited second step. This rule applies to new or modified production code; unrelated legacy code need not be mass-refactored.

