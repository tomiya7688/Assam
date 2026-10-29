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

## Shared inheritance policy (mandatory and review criteria)

### Prohibited: continued inheritance rooted in a concrete class

- **If class B inherits from a concrete class A, class C must not inherit from B**: `concrete A → B → C` is forbidden even when B is abstract.
- **`abstract A → concrete B → C` does not violate this prohibition.** It still requires a design/readability review.
- A direct `concrete A → B` inheritance is not universally prohibited by this rule alone. An existing stricter project rule banning all inheritance from concrete classes continues to take precedence.
- Implicit language root types such as `Object`, `System.Object`, `java.lang.Object`, and interface implementation/inheritance do not count for this prohibition.

### Design principles before inheriting

- **Avoid inheriting from classes that contain concrete behavior by default**, including abstract classes with concrete implementations. Prefer delegation/composition if inheritance has no intrinsic domain or type meaning and only reuses code.
- Introduce inheritance only for a meaningful shared shape/contract that already exists or is reasonably expected to arise. Do not invent inheritance hierarchies solely for hypothetical reuse.
- Even if formally permitted, reject inheritance during review when it harms readability, blurs responsibilities, increases change propagation unreasonably, or violates substitutability. Passing the strict prohibition is not design approval.

### Applicability and exemptions

- A project may explicitly document an intentional hierarchy, its rationale and exact scope as a design exception. Existing code alone is not enough evidence.
- Do not conflate a compiler/analyzer's supported source-language inheritance, examples, or test fixtures with the project's own implementation rules.
- Apply to new and modified project-owned implementation code. Do not mass-refactor unrelated legacy code.
