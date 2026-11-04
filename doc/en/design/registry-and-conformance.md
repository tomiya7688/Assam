# Registry and conformance

Language: [日本語](../../jp/設計/レジストリとconformance.md) | English

Target issues: #2 (machine-readable schema), #13 (CI gates), #8 (conditional branches). Decisions: DEC-10, PRO-07, PRO-11.

## 1. Role

The registry is the canonical source of **instruction contracts and mapping information** and contains no execution logic. Implementations (Python/Go/Java/Rust) use the registry by loading it or by code generation, and do not keep their own opcode, operand arity, or effects. The semantics themselves are canonical in [Core semantics](core-semantics.md); the registry holds a machine-readable summary of them and links.

## 2. Registry schema v3

The current v2 has the effects of the Core Draft (read/write positions, memory effects, integer-parameter positions, trap conditions, `target_mapping_id`, flow), but width/signedness is `not_decided` and Full names and Core names are mixed. v3 satisfies the following.

```jsonc
{
  "schema_version": 3,
  "profiles": {
    "full": {},
    "core": { "versions": ["1"] },
  },
  "instructions": [
    {
      "id": "core.add", // identifier stable across versions
      "mnemonic": "add", // canonical (lowercase in Core)
      "aliases": [], // empty for Core/canonical. Full side uses full_names
      "availability": [
        { "profile": "core", "since": "1" },
        { "profile": "full" },
      ],
      "full_names": ["Add", "add"], // case-insensitive spellings in Full
      "operands": [
        { "role": "dest", "kind": "register", "access": "write" },
        { "role": "src", "kind": "register", "access": "read" },
        { "role": "src", "kind": "register", "access": "read" },
      ],
      "width": { "bits": 64, "signedness": "agnostic" }, // "signed" | "unsigned" | "agnostic"
      "effects": {
        "registers": "by_operand",
        "memory": { "read": false, "write": false, "width_bits": null },
        "control": "next", // next | jump | conditional | link | indirect | halt | trap
      },
      "traps": [], // e.g. ["div_by_zero"]
      "semantics": "doc/en/design/core-semantics.md",
      "target_mapping_id": "assam.core.1.add",
      "classification": "ordinary", // ordinary | abi_primitive
    },
  ],
}
```

Key points:

- `id` is immutable across versions. A change that alters meaning is expressed as a **new core version** with a separate entry (or a split of `availability`).
- `kind` is one of `register` / `immediate` / `symbol` (label) / `memory_offset` / `helper_id` / `trap_code`. A range (`min`, `max`) can be held on the operand side.
- `mnemonic` is the official spelling. Full aliases are confined to `full_names`, and the Core parser does not consult them ([grammar](core-grammar-and-profile.md)).
- `target_mapping_id` includes the version (`assam.core.1.<name>`). The Draft's `assam.core.draft.*` is retired, and mapping tables are made per version.
- `classification: abi_primitive` is the exception class for three-target coverage (`hcall`, etc.). Ordinary opcodes without a classification must be covered for all three targets, as required by CI.
- The execution-handler identifier is specific to the Python implementation, so it is removed from the registry and moved to a table on the Python side that maps `id` -> implementation. The registry does not decide how execution is done.

### 2.1 Migration

| Item        | Policy                                                                                                                                                             |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| v2 -> v3    | No conversion script; write v3 by hand and regression-verify in `tests` that "Full instructions are accepted/rejected the same as in v2"                           |
| Coexistence | For a period, ship only `instruction_registry.json` (v3). Reading v2 is limited to tests used for checking past mapping tables, and is deleted when v3 is complete |
| schema      | Add `instruction-registry-v3.schema.json` and validate the registry itself against the schema                                                                      |

### 2.2 Validation (reject before execution)

- Schema validation (add the development dependency `jsonschema` to a dev extra; the runtime remains standard library only).
- Consistency checks: no duplicate `id` or `mnemonic`, no `full_names` collisions, `traps` within the trap kind enumeration of the Core semantics, no duplicate `target_mapping_id`, and every `ordinary` instruction has an `in_scope` declaration for all three targets.
- "In the registry" = "validated before reaching the runtime switch". Unknown/invalid instructions are rejected at VM construction (#2).

### 2.3 Use from Go and other languages

- The registry is distributed as a standalone JSON, pinned by git tag (`registry-v3.N`) and sha256. The Go side imports it via `go:embed` or as a generated artifact, and pins the sha256 in a test.
- On change, CI that re-runs the entire conformance corpus whenever the registry's sha256 changes is required (drift detection).
- Future code generation can be added as `assam registry export --format <go|json>`, but the output must be deterministically identical.

## 3. Conformance corpus

### 3.1 Location and format

Place one case per JSON file under `examples/conformance/`. Multiple VMs and translation results read the **same file**.

```jsonc
{
  "schema_version": 1,
  "id": "core1.branch.beq.false-no-side-effect",
  "category": "execution", // parse | execution | translation
  "profile": { "name": "core", "version": "1" },
  "description": "...",
  "source": { "text": "const r1, 1\n..." }, // or {"ir": {...}}
  "environment": {
    "memory_bytes": 4096,
    "memory_segments": [],
    "max_steps": 10000,
  },
  "expect": {
    /* per category */
  },
}
```

- `parse`: the expectation is `{"accepted": true, "canonical": "..."}` or `{"accepted": false, "diagnostics": [{"code","line"}]}`.
- `execution`: the expectation is the observed JSON of [Core semantics, section 3](core-semantics.md) (`status`, `trap`, `registers`, `memory_sha256`).
- `translation`: the expected instruction sequence (golden) per target/profile. Execution equivalence is separate ([target translation](target-translation.md)).
- The current `examples/conformance/conditional-branches.json` (for Draft/Full) is migrated to the new format and kept, with Full stated explicitly in `profile`.

### 3.2 Required categories

1. Normal values, boundary values, and `r0` for all instructions
2. All traps and "no side effects on trap"
3. Conditional branches: both paths, official names/aliases (Full only), immediate/register, forward/backward labels, no side effects on the non-selected path (#8)
4. Memory widths, sign extension, unaligned access, out of range, wraparound (a 1-byte load with `rbase = 2^64-1`, `off = 1` succeeds with `ea = 0`; wraparound of `ea + w` traps)
5. Nested calls and returns via `jal`/`jr`
6. Parsing (canonical round-trip, diagnostic codes)
7. Full compatibility (#10 string operand round-trip, aliases)
8. Representative lowering sequences for x\*/checked overflow (produced by the backend side, but verifying correct behavior as Core)

### 3.3 Execution protocol

Each implementation prints the observed JSON to standard output via `<impl> conformance-case <case.json>`. `assam conformance run --impl <cmd>` runs all cases, compares against expectations, and reports differences. The Python reference implementation is the default for `assam conformance run`. On a difference, the **reference implementation is authoritative**, but if the reference implementation contradicts a DEC/the design, the design takes precedence and the reference implementation is fixed.

## 4. CI gates (#13)

The following are required on PRs and pushes to main. They are added to the current set (pytest, Ruff formatting of changed Python files, pip/certificate checks, mapping-table checks).

| Gate                 | Content                                                                                                      | Status                                                               |
| -------------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| Tests                | `pytest` (Python 3.10/3.12)                                                                                  | Done                                                                 |
| Formatting           | `ruff format --check` on changed Python files                                                                | Done                                                                 |
| Document formatting  | `prettier --check` for Markdown/YAML (changed files)                                                         | Described in the operating workflow. If not installed, install in A2 |
| Syntax/import check  | `python -m compileall -q assam tests` and import of all modules                                              | A2                                                                   |
| Package smoke        | Build wheel/sdist, install into a separate venv, and confirm `assam --help` and the presence of bundled data | A2                                                                   |
| CLI smoke            | Minimal cases for `parse`/`json`/`run`/`analyze`/`from-c`                                                    | A2                                                                   |
| malformed corpus     | Invalid input is rejected with `ValueError`/diagnostics, and raw `TypeError`/`KeyError` do not leak          | A2 (prevents recurrence of #11 and #12)                              |
| Deterministic replay | Running the same input twice yields identical observed results                                               | A2                                                                   |
| schema validation    | Schemas of the registry, IR, mapping tables, and manifest                                                    | B3                                                                   |
| conformance          | The entire corpus (reference implementation). Required when the registry changes                             | B5                                                                   |
| Mapping coverage     | Three-target coverage declaration and mapping-table check (current). Rebuilt for v1 instructions             | C3                                                                   |
| Type checking        | Not adopted at present (standard library only, small scale). If adopted, fix it in a design PR               | Not adopted                                                          |

A failing change is not treated as green: configuring branch protection to make checks required is the work of a human (repository administrator). Until it is configured, "CI success is a merge condition" is observed operationally in the workflow.

## 5. Acceptance criteria

- WP-B3: registry v3 and its schema, definitions of all v1 instructions, consistency checks, and regression verification against v2 pass.
- WP-B5: corpus format, runner, an initial set of the required categories (1-7 above), and CI enforcement.
- WP-A2: all A2 gates above are in CI, and the PR has a record confirming that they fail on deliberately broken input.
