# Overall Design

Language: [日本語](../../jp/設計/全体設計.md) | English

Status: canonical design (consolidates Issues #1-#6, #10, #13-#15, #28, #29). For individual decisions, see the [decision log](decision-log.md).

## 1. Purpose and positioning

ASSAM consists of **Full ASSAM**, which has conveniences for humans, and **Assam Core**, a strict low-level subset that machines generate and process. Core is the common boundary of the following chain.

```text
Bitlang Low
    -> Bitlang VM Backend
    -> Assam Core (canonical text / JSON IR)
    -> Bitlang VM (Go, primary runtime)
    -> x64 / ARM64 / RISC-V translation (JSON mapping tables)
    -> (later) Wasm / JVM bytecode translation
```

Assam provides:

1. Core's **grammar, semantics, and version contract** (the canonical sources are the documents and the registry/schema)
2. A reference implementation (Python parser / VM / analyzer / CLI)
3. A machine-readable **instruction registry**, and the verification, translation, and conformance infrastructure that uses it
4. A verification infrastructure for declarative **target mapping tables**, plus the bundled Draft/official tables

## 2. Design principles

1. **One source of truth**: opcodes, operands, effects, traps, and versions live in the registry/schema. Duplication per implementation language is prohibited (DEC-10).
2. **Keep Core small**: a new opcode must be declaratively mappable to the three targets and must have explicit effects and traps. Do not add one solely for host or specific-CPU convenience.
3. **Fail-closed**: invalid or ambiguous input is diagnosed and rejected before execution. No silent correction, approximation, or implicit halting.
4. **Host independence**: do not leak Python's arbitrary-precision integers, Java's Object references, Rust's panic, etc. into guest semantics.
5. **Do not mix Full and Core**: compatibility aliases and high-level instructions are Full only. Do not let them into Core validation results.
6. **Compare by observation**: implementation correctness is judged by matching observed results (registers, memory, trap) against the shared conformance corpus.
7. **Do not claim what cannot be verified**: structural checks (coverage declarations, reference consistency) are distinct from semantic equivalence. If the latter is unverified, do not write "done".

## 3. Profile system

| profile | version | status                        | description                                                                                                                                                    |
| ------- | ------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `full`  | current | maintained                    | PascalCase, case-insensitive, whitespace-separated, r0-r31 (typed operands since WP-B1), Push/Pop, terminal instructions. Backward compatibility is maintained |
| `core`  | `draft` | **to be deprecated**          | The current Draft. r0-r31 (since WP-B1), arbitrary-precision integers, hidden call stack, sparse memory. Deprecated when Core v1 is complete (Q4)              |
| `core`  | `1`     | **new implementation target** | Bitlang VM Core v1 consumer contract. [Grammar](core-grammar-and-profile.md), [semantics](core-semantics.md)                                                   |

The JSON IR profile marker (`{"name","version","registry_schema_version"}`) continues and is made able to express `core`/`1` (registry schema v3, [registry](registry-and-conformance.md)). Existing JSON without a marker remains `full`.

## 4. Current state vs. target gaps

| Item                   | Current (main)                                         | Target (Core v1)                                                           | Owner WP    |
| ---------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------- | ----------- |
| Syntax                 | PascalCase, mixed whitespace/comma separators, aliases | lowercase, mandatory commas, no aliases                                    | WP-B2       |
| Operand representation | strings turn into numbers/registers (#10)              | register/immediate/symbol distinguished by type; preserved in IR           | WP-B1       |
| Registers              | r0-r15, ordinary registers                             | r0-r31, 64-bit, r0=0                                                       | WP-B4       |
| Integers               | Python arbitrary precision, width/sign undecided       | modulo 2^64, signed/unsigned instructions distinguished                    | WP-B4       |
| Memory                 | sparse, unwritten read=0, no width                     | contiguous byte space, explicit width, LE, out-of-range trap               | WP-B4       |
| Calls                  | hidden call stack                                      | link register (jal/jr)                                                     | WP-B4       |
| Traps                  | `VMError` strings                                      | stable classification, location, code                                      | WP-B4       |
| registry               | schema v2, width/sign are `not_decided`                | schema v3, all v1 instructions machine-readably defined                    | WP-B3       |
| Translation            | Draft tables (structural checks only)                  | three-target tables for v1 instructions + fixtures + execution equivalence | WP-C1 to C4 |
| CI                     | pytest, ruff, pip check, mapping table check           | + package smoke, CLI smoke, malformed corpus, conformance, schema          | WP-A2       |
| Distribution           | unsigned                                               | artifact digest + attestation                                              | WP-A3       |

## 5. Component structure

```text
assam/
  parser.py          Full-compatible parser and Core canonical parser (separate)
  ir.py              Program / Instruction / typed Operand (extended in B1)
  instruction_set.py registry loading and per-profile validation
  profile.py         profile identifiers and IR marker
  vm.py              Full VM / Core v1 VM (separate classes, separate files)
  analyzer.py        static analysis
  c_frontend.py      C subset -> Core v1 canonical
  target_coverage.py coverage declarations and mapping table checks
  translator/        (from C1) loader, template expander, encoder boundary
  data/              registry and schemas (canonical)
examples/
  conformance/       shared conformance corpus
  targets/           bundled mapping tables
```

Follow the one-class-per-file, one-responsibility rule. Because Full and Core v1 differ in semantics, make the VMs **separate classes**, and share common parts by delegation/composition rather than inheritance (see the inheritance rules in the [coding rules](../coding-rules.md)).

## 6. Roles of implementation languages (DEC-14)

| Language | Role                                                                         | Status                                                |
| -------- | ---------------------------------------------------------------------------- | ----------------------------------------------------- |
| Go       | Primary runtime (Bitlang VM). Bootstrap/reference until future self-hosting  | Separate repository. Uses Assam's registry/corpus     |
| Python   | Parser, reference VM, conformance baseline, verification tools               | This repository                                       |
| Java     | Independent Java-based VM (#14). Separate from JVM bytecode translation (#6) | Future. [Additional runtimes](additional-runtimes.md) |
| Rust     | Safety-focused native VM candidate (#15)                                     | Future. Same as above                                 |

None of these is "something that automatically guarantees complete safety"; FFI, native extensions, and implementation bugs remain separate verification targets.

## 7. Phases and dependencies

```text
Phase A  Foundation: A1 pip/certifi(#28) -- A2 CI gates(#13) -- A3 signing/attestation(#29)
Phase B  Contract:   B1 operand types(#10) -> B3 registry v3(#2) -> B2 Core grammar(#1) -> B5 conformance -> B4 semantics+VM(#3) -> B6 migration
Phase C  Translation: C1 mapping schema v2/loader(#4) -> C2 three-target tables -> C3 coverage CI -> C4 translation execution equivalence -> C5 custom targets
Phase D  Future:     D1 Wasm(#5), D2 JVM(#6), D3 Java VM(#14), D4 Rust VM(#15)
```

For detailed work packages, dependencies, and acceptance criteria, see the [implementation plan](implementation-plan.md). Phase A takes priority over feature development (#28 and #29 are P0). Phase D presupposes completion of Phase B (contract + conformance + CI) and stable three targets in Phase C.

## 8. Non-goals

- Adding high-level instructions (string handling, terminal, allocation, closures, ownership) to Core
- Re-analyzing Bitlang's MIR/ownership/borrow etc. (neither the translator nor Core does this)
- Embedding a general-purpose programming language in JSON mapping tables
- Turning execution logic into JSON (the registry holds only instruction contracts and mapping information)
- Making x* (arbitrary precision) or Float a single instruction (x* is explicit lowering; Float is out of scope for v1)
- Changing the specification for the sake of the Java/Rust VMs

## 9. Risks and mitigations

| Risk                                                                                    | Mitigation                                                                                                                                    |
| --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Draft -> v1 breaks existing tests and the C frontend                                    | Implement Full and Core v1 separately, and make switching the C frontend output an independent WP                                             |
| Semantic drift between implementations                                                  | Make the conformance corpus the sole comparison baseline, and require running the full corpus in CI when the registry changes                 |
| Mapping tables treated as done while only structurally checked and semantics unverified | Always include the verification scope name (`validation_scope`) in reports, and separate C4 (execution equivalence) as a completion condition |
| Divergence between design and implementation                                            | Fix divergence first in a design PR. Put "design references" and a "Definition of Ready" on each WP                                           |
| P0 supply-chain issues buried under feature development                                 | Fix Phase A at the front, and do not release until A1-A3 are complete                                                                         |
