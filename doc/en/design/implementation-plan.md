# Implementation Plan

Language: [日本語](../../jp/設計/実装計画.md) | English

This splits the canonical design documents ([Overall design](overview.md) and others) into 1 work unit = 1 branch = 1 PR = 1 feature. An assignee (human or AI) can start implementing by reading **only their own WP row and the linked sections**.

## 1. Common Rules

**Before starting (Definition of Ready)**

1. `git fetch`/`pull --rebase` done per the [workflow](../workflow.md).
2. The "Prerequisite" of the target WP is already in `main`. If not, do not start.
3. The open items in the "Blocked by" column ([Decision log](decision-log.md)) are settled. If undecided, decide first.
4. Read the "Design reference" and confirm the acceptance criteria can be turned into implementation and tests. If the design is insufficient or contradictory, **do not start implementing; fix it first in a design PR**.

**Completion (Definition of Done)**

1. Each acceptance criterion has a corresponding test (write the test name or `tests` path in the PR).
2. Update the relevant documents (specs, registry description, roadmap, both Japanese and English) in the same PR.
3. CI passes, self-review is done, and unverified items are stated as "unverified".
4. Design deficiencies found during work are reflected in the decision log/design documents (do not fix only the code and call it done).

**PR size**: 1 PR = 1 WP (split large WPs into a/b). Do not mix in unrelated formatting or renames.

**Assignment guideline** (follow the Issue's agent-routing note): WPs involving design decisions on grammar, semantics, ISA, or mapping tables go to the senior assignee (who leads design decisions and verification). Routine implementation with settled specs (adding tests, documentation, simple porting) may be delegated to lightweight assignees. Completion is judged by the senior assignee.

## 2. List of Work Units

| WP  | Title                                             | Issue   | Prerequisite      | Blocked by            | Priority |
| --- | ------------------------------------------------- | ------- | ----------------- | --------------------- | -------- |
| A1  | Confirm completion of Python certificate handling | #28     | —                 | —                     | P0       |
| A2  | Expand CI gates                                   | #13     | —                 | —                     | P0       |
| A3  | Release signing / attestation                     | #29     | A1                | —                     | P0       |
| B1  | Typed operands and Full string preservation       | #10     | A2 (smoke only)   | —                     | High     |
| B3  | registry schema v3                                | #2      | B1                | —                     | High     |
| B2  | Core v1 canonical parser/emitter                  | #1      | B1, B3            | —                     | High     |
| B5  | conformance corpus and runner                     | #8, #13 | B3                | —                     | High     |
| B4  | Core v1 reference VM                              | #3      | B2, B3, B5        | —                     | High     |
| B6  | C frontend, analyzer, Draft removal               | #1, #3  | B4                | Q4                    | Medium   |
| C1  | Mapping table schema v2, loader, expander         | #4      | B3                | —                     | Medium   |
| C2  | x64/ARM64/RISC-V v1 tables (L1-L3)                | #4      | C1, B4            | —                     | Medium   |
| C3  | v1 coverage CI gate                               | #4, #2  | C2                | —                     | Medium   |
| C4  | Translation execution equivalence (L4)            | #4      | C2, B5            | Execution environment | Medium   |
| C5  | Custom/FPGA target example and docs               | #4      | C1                | —                     | Low      |
| D1  | Wasm translation                                  | #5      | C3, B5            | —                     | Later    |
| D2  | JVM bytecode translation                          | #6      | C3, B5            | —                     | Later    |
| D3  | Java VM                                           | #14     | B5, C3            | —                     | Later    |
| D4  | Rust VM                                           | #15     | B5, C3            | —                     | Later    |
| X1  | Issue cleanup (close #8, status updates)          | #7-#12  | B5 (basis for #8) | —                     | Low      |

Dependency diagram:

```text
A1 ─ A3
A2 ─ B1 ─ B3 ─ B2 ─┐
            └ B5 ──┼─ B4 ─ B6
                   │
         B3 ─ C1 ─ C2 ─ C3 ─ (D1, D2, D3, D4)
                     └ C4 (B5 also required)
                     C1 ─ C5
```

## 3. Each Work Unit

### A1 Confirm completion of Python certificate handling (#28)

- Design: [Distribution and supply chain §3](supply-chain.md)
- Current: CI bootstraps pip 26.2.2 with a pinned hash, and the CA bundle check is introduced. In progress on a separate branch.
- Done: record in the PR that the completion criteria of #28 are met (list of Python/venv, CA bundle, and versions checked). Confirm `uv`/`sigstore` are unused.
- Tests: extend `tests/test_pip_ca_bundle.py` (existing).

### A2 Expand CI gates (#13)

- Design: [Registry and conformance §4](registry-and-conformance.md)
- Deliverables: in `.github/workflows/ci.yml`, compileall and import checks, wheel build + install smoke in a separate venv, CLI smoke, malformed corpus (`tests/test_malformed_inputs.py`), deterministic replay test.
- Acceptance: confirm CI fails on intentionally broken input and a broken package, and record it in the PR. Raw `TypeError`/`KeyError` must not leak to users.
- Notes: keep the existing Ruff formatting, pip check, and mapping table check.

### A3 Release signing / attestation (#29)

- Design: [Distribution and supply chain §2](supply-chain.md)
- Deliverables: `.github/workflows/release.yml`, `SHA256SUMS` generation, attestation, verification step, README verification steps.
- Acceptance: attestation and verification succeed in a dry run (no tag, draft release via `workflow_dispatch`). The actual release is an administrator (human) task of pushing a tag.

### B1 Typed operands and Full string preservation (#10)

- Design: [Core grammar and profile contract §2](core-grammar-and-profile.md)
- Deliverables: `Operand` type in `assam/ir.py`, quote/comment detection fix in `assam/parser.py`, `program-ir-v2.schema.json`, v1 IR load normalization, `vm.py` branching on `kind`.
- Acceptance: the acceptance criteria of #10 (4 items). All existing Full tests pass. Ambiguous v1 IR is rejected. The Full register range is widened to `r0`-`r31` (for Core -> Full syntactic compatibility).
- Tests: `tests/test_operand_kinds.py` (empty string, number-like, register-like, `;`/`#`, escapes, round trip).
- Note: minimally fix the C frontend and analyzer to handle typed operands (behavior unchanged).

### B3 registry schema v3 (#2)

- Design: [Registry and conformance §2](registry-and-conformance.md), [Core semantics §2](core-semantics.md)
- Prerequisite decision: Q1 is decided ([PRO-16](decision-log.md); `mulhu`/`mulhs` are included).
- Deliverables: `assam/data/instruction_registry.json` (v3), `instruction-registry-v3.schema.json`, updated loading in `assam/instruction_set.py`, consistency checks, regression tests against v2 (acceptance/rejection of Full instructions unchanged).
- Acceptance: schema validation, consistency checks, Full regression, all v1 instructions (about 45) defined. `handler` leaves the registry and becomes a Python-side table.

### B2 Core v1 canonical parser/emitter (#1)

- Design: [Core grammar and profile contract §3-§5](core-grammar-and-profile.md)
- Deliverables: `assam/core_parser.py` (Core-specific, one class per file), `assam/core_emitter.py`, diagnostic classes, IR stamp `core/1`.
- Acceptance: negative cases per diagnostic code, golden round trip, Core -> Full upward-compatibility tests, `assam json --profile core` handles v1.
- Tests: `tests/test_core_parser.py`, `tests/test_core_emitter.py`, `tests/test_core_in_full.py`.

### B5 conformance corpus and runner (#8, #13)

- Design: [Registry and conformance §3](registry-and-conformance.md)
- Deliverables: new format under `examples/conformance/`, migration of existing `conditional-branches.json`, `assam conformance run`, the `conformance-case` protocol, initial corpus (build parse/Full execution first).
- Acceptance: the runner compares expected and actual, and exits non-zero on mismatch. Corpus format schema. Core v1 execution cases are added in parallel with B4 (B4 follows this via TDD).

### B4 Core v1 reference VM (#3)

- Design: [Core semantics](core-semantics.md)
- Prerequisite decision: Q1 is decided (PRO-16).
- Deliverables: `assam/core_vm.py` (a class separate from the Full VM), observation JSON generation, trap kinds. The Full VM is not changed.
- Acceptance: [Core semantics §7](core-semantics.md). All instructions, all traps, boundary values, and no side effects on trap are verified by the corpus.
- Tests: via the corpus (`tests/test_conformance.py` runs all cases) plus unit tests.

### B6 C frontend, analyzer, Draft removal (#1, #3)

- Prerequisite decision: Q4.
- Deliverables: v1 canonical output from `c_frontend.py` (the return value of `main` is placed in `r1` and then `halt`; `r0` cannot be used because it is the constant 0 in v1. This convention belongs to the C frontend specification, not the Core semantics. Variables -> `const`/`mov`), v1 support in `analyzer.py`, removal of Draft Core (`draft`), v1-ification of `doc/*/assam-core.md` and `instruction-set.md`, roadmap update.
- Acceptance: `examples/sum.c` is converted to v1 and returns 42 on the Python v1 VM. IR stamped Draft is rejected with a diagnostic and a migration notice.

### C1 Mapping table schema v2, loader, expander (#4)

- Design: [Target translation §1-§3](target-translation.md)
- Deliverables: `assam/data/target-mapping-v2.schema.json`, `assam/translator/` (loader, expander, allocator, encoder-boundary interface), v2 support in `assam/target_coverage.py`.
- Acceptance: unit tests of symbolic expansion, restricted set of `when` predicates, explicit diagnostics for unsupported instructions.

### C2 Three-target v1 tables (#4)

- Deliverables: `examples/targets/{x86-64,arm64,riscv64}-*-v1.{mapping,coverage}.json` and representative fixtures (golden). Replacement of the Draft tables.
- Acceptance: L1-L3. Target-specific difficulties ([Target translation §5](target-translation.md)) declared in the tables. State that semantic equivalence is unverified (L4 is C4).

### C3 v1 coverage CI gate (#4, #2)

- Deliverables: three-target coverage in CI, rejection of uncovered ordinary opcodes, `abi_primitive` classification.
- Acceptance: confirm and record that CI fails when one ordinary opcode is added without table entries.

### C4 Translation execution equivalence (#4)

- Prerequisite: an execution environment (qemu etc.). If unavailable, record it as not reached with the reason, and state the skip explicitly.
- Deliverables: a job/script that executes translation results on the target and compares with the observation JSON.
- Acceptance: observations of representative programs match the reference VM (to the extent the environment is available).

### C5 Custom/FPGA targets (#4)

- Deliverables: a minimal custom target table example, a "how to write" guide in `doc`, tests for diagnostic examples of unsupported instructions.

### D1-D4 Future

- Design: [Target translation §7-§8](target-translation.md), [Additional runtimes](additional-runtimes.md).
- At the start, confirm the Definition of Ready in the first PR, and precede with detailed design PRs (scheme, location, language version).

### X1 Issue cleanup

- #8: In the current main, fallthrough for conditional branches is already fixed, and `tests/test_conditional_branch.py` and shared cases exist. Close with justification once migrated to the new-format corpus in B5 (closing requires human confirmation).
- #7, #9, #11, #12: Already closed. Regression prevention is covered by A2's malformed corpus and B5.

## 4. Operating Rules to Prevent Rework

1. When unsure, read the [decision log](decision-log.md) -> design documents -> Issue, in that order. Judgments not in the decision log are left in the PR as a "decision memo", and the decision log is updated if needed.
2. If design and implementation conflict, submit a PR fixing the design (reviewed by a human) before fixing the implementation.
3. Do not change several of registry, IR, VM, and mapping tables in one PR. Proceed in the order contract (registry/schema) -> parser -> VM -> translation, landing each prerequisite in `main` before moving on.
4. Changes to compatibility contracts (trap kind, diagnostic code, registry `id`, observation JSON, IR schema) go design PR -> implementation PR.
5. Completion reports must state the check tier (L1-L4, structure/semantics) and unverified items.
