# Assam Core Profile

Language: [日本語](../jp/assam-core.md) | English

Status: Draft

Assam Core is the strict low-level profile of ASSAM used by execution targets such as Bitlang VM.

It is **not a separate language**. Full ASSAM may grow higher-level conveniences, pseudo-instructions, generators, debugger directives, or transformation features, while Assam Core remains the stable assembly boundary that machines and backends can generate and consume directly.

## Primary consumer

Bitlang VM uses Assam Core as the syntax and instruction-profile basis of Bitlang VM Assembly.

The normal Bitlang VM path is:

```text
Bitlang Low
    -> Bitlang VM Backend
    -> Assam Core / Bitlang VM Assembly
    -> Bitlang VM
    -> x64 / ARM64 / RISC-V architecture translation
```

Because Bitlang Low is a primary producer, Core must be easy to generate deterministically and must not require a backend to synthesize human-oriented high-level ASSAM features.

## Required architecture portability

Assam Core is intentionally designed as a small common instruction layer that can be translated mechanically to multiple real ISAs.

The mandatory initial architecture targets are:

- x64 / x86-64
- ARM64 / AArch64
- RISC-V

The mapping for these targets must be described primarily by **JSON translation tables**. A mapping entry may expand one Core instruction into multiple target instructions when necessary, but the meaning of the Core operation must remain small enough that translation is mechanical rather than a second high-level compiler.

Additional targets are intentionally open-ended. Assam does not need first-party code for every custom CPU or FPGA design. A developer may add support for an FPGA-oriented ISA, soft-core CPU, experimental processor, or other custom target by writing a compatible JSON mapping table for that target.

The intended extension model is therefore **data-driven**: if the target can express Assam Core operations, the developer supplies the correspondence table directly. Such community/custom targets are not part of the mandatory x64 / ARM64 / RISC-V acceptance gate unless they are later promoted to first-party supported targets.


## Future official bytecode targets

After the mandatory x64 / ARM64 / RISC-V architecture translators are stable, Assam should also provide official translation paths for:

- WebAssembly (Wasm)
- JVM bytecode

These are **later-phase targets** and are not part of the initial Assam Core stability/acceptance gate.

Wasm and JVM bytecode are not treated as ordinary native-ISA JSON mappings. Both are stack-oriented execution formats, and Wasm additionally requires structured control flow while JVM bytecode has verifier/type-stack and class/method constraints.

The intended translation model is:

```text
Assam Core
    -> target-specific normalization / CFG + stack lowering
    -> Wasm or JVM bytecode mapping/emission
```

The generic JSON mapping data may still describe simple arithmetic, comparison, conversion, and other opcode correspondences where useful. However, target-specific lowering is permitted for structural requirements that cannot be represented safely as a simple instruction table.

This does not weaken the Core simplicity rule. The Wasm/JVM translators must adapt the simple Core program to the target model; Assam Core must not grow Wasm-specific or JVM-specific compound instructions merely to simplify those translators.

### WebAssembly

The future Wasm translator must handle, at minimum:

- Core register/value flow to Wasm locals/operand stack;
- arbitrary Core CFG to valid structured Wasm control flow or another semantics-preserving lowering;
- linear-memory mapping for guest memory;
- calls, returns, traps, and runtime helpers;
- deterministic integer-width semantics required by the selected Assam/Bitlang profile.

### JVM bytecode

The future JVM-bytecode translator must handle, at minimum:

- Core register/value flow to JVM locals/operand stack;
- JVM verifier-compatible stack and type states;
- labels, branches, calls, and returns;
- guest memory through an explicit runtime representation rather than pretending JVM object references are raw guest pointers;
- generated class/method structure and runtime helper boundaries;
- semantics-preserving lowering for operations not directly represented by JVM bytecode.

Neither target translator may reconstruct Bitlang source-level ownership, borrow, class, or other high-level semantics.

## Core design rules

1. One instruction has one explicit low-level effect.
2. Control flow is explicit.
3. Memory effects are explicit.
4. Runtime failures use defined trap/error behavior rather than host-language accidents.
5. No implicit ownership, cleanup, allocation, dynamic dispatch, closure capture, or other high-level language behavior exists in Core.
6. Pseudo-instructions and convenience syntax may exist in full ASSAM only when they lower deterministically to Core.
7. Core instruction semantics are versioned and machine-readable.
8. Parsers, VMs, and translators should consume the same canonical instruction definition rather than maintaining unrelated opcode tables.
9. Target translators may map one Core operation to multiple target instructions when the target ISA cannot express the required semantics directly.
10. A new Core instruction must be simple enough to define mappings for x64, ARM64, and RISC-V, unless it is an explicitly specified runtime/VM ABI primitive.
11. If a proposed operation requires substantial architecture-specific semantic lowering, it must normally be decomposed into simpler Core instructions before architecture translation.
12. Core must not contain an instruction merely because it is convenient for the ASSAM interpreter or for one particular CPU architecture.

## Instruction simplicity gate

Assam Core is deliberately closer to a portable micro-operation / RISC-like layer than to a feature-rich assembly language.

Before an instruction is admitted to Core, its design review must answer:

- Can its operands and effects be stated without hidden high-level state?
- Can x64, ARM64, and RISC-V mappings be expressed in JSON as a small instruction sequence plus explicit operand adaptation?
- Are all memory effects visible?
- Are all control-flow effects visible?
- Are failure/trap conditions explicit?
- Would a target translator need to reconstruct source-language concepts to implement it?

If the final answer is no for the mapping questions or yes for the reconstruction question, the operation should normally be lowered into smaller Core operations instead.

Examples of functionality that belongs outside Core unless reduced to primitives include high-level terminal/device commands, implicit object operations, compound resource management, closure operations, language-level allocation policy, or complex convenience instructions. Full ASSAM may expose such features as pseudo-instructions, but they must lower before Core translation.

## JSON architecture mapping contract

The architecture mapping data must be machine-readable and versioned.

As a first step before defining translation templates, the [target-mapping-coverage-v1.schema.json](../../assam/data/target-mapping-coverage-v1.schema.json) defines a coverage-manifest format. For each target/profile it declares each `target_mapping_id` as `in_scope` or `out_of_scope`; the latter requires a reason. `in_scope` does not mean a translation sequence has been implemented. This schema alone does not check completeness against the registry or duplicate IDs.

`assam check-target-coverage <manifest.json>` checks the required manifest v1 structure, then compares it with the bundled Core registry to ensure every Core hook ID appears exactly once, with no unknown IDs or duplicates. Use `--registry <registry.json>` to check against another registry, or `--format json` for machine-readable output. The result's `validation_scope` is `coverage_declarations_only`; mapping implementation and executability are not checked.

`assam check-target-matrix <x64.json> <arm64.json> <riscv.json>` checks each manifest's coverage declaration and requires all three initial targets (aliases `x86-64`, `AArch64`, and `RISC-V`). Custom-target manifests may also be supplied; use `--format json` for machine-readable output. The result's `validation_scope` is `coverage_declarations_only`; it does not prove that an `in_scope` translation is implemented or executable.

`assam scaffold-target-coverage <architecture> <profile>` prints a JSON template containing every Core hook ID. Every entry defaults to reasoned `out_of_scope`, so authors must review and explicitly reclassify each item. Template generation and matrix checking do not claim that mappings are implemented.

The minimal structure for mapping data is draft-defined by [target-mapping-v1.schema.json](../../assam/data/target-mapping-v1.schema.json). Each Core hook ID can declare a sequence of target opcodes whose operands reference Core operands, immediates, target registers, scratch names, or symbols. This schema validates JSON shape only. It does not validate semantic equivalence, register allocation, constraints, branch conditions, width/signedness variants, ABI helpers, or completeness against the Core registry. It is not an executable translation contract, and an `in_scope` coverage declaration still does not mean that a mapping is implemented.

`assam check-target-mappings <mapping.json>` checks this structure, Core registry hook references, and duplicate IDs. Each zero-based `core_operand.index` must be less than the corresponding Core instruction's operand count, including when another registry is selected with `--registry`. Machine-readable output via `--format json` includes `validation_scope: "mapping_structure_and_registry_references_only"`. Omitted Core hooks are listed in JSON and counted in text output. This command does not validate mapping semantics or executability.

`assam check-target-mappings <mapping.json> --coverage <manifest.json>` also validates the complete manifest against the same registry and requires the mapping hook set to equal its `in_scope` declarations. Missing `in_scope` sequences and sequences for `out_of_scope` hooks are errors. Architecture identities use the same aliases as the matrix checker; profile strings must match exactly. JSON output uses `validation_scope: "mapping_structure_registry_references_and_coverage_only"` and includes the declaration report under `coverage`. This checks sequence presence and reference consistency; semantic and execution equivalence still require separate verification.

At minimum, each target mapping must be able to describe:

- Core opcode/profile version;
- target architecture/profile;
- operand correspondence and constraints;
- one-to-one or one-to-many target instruction templates;
- immediate/register restrictions;
- required temporary/scratch resources when expressible declaratively;
- condition-code or branch relation mapping;
- width/signedness variants;
- unsupported combinations that require prior Core decomposition;
- target ABI/helper call identifiers where a defined runtime boundary is required.

The mapping table is not a place to embed an unrestricted programming language. If a mapping requires complex semantic code, Core should first be simplified or decomposed.

### Custom / FPGA target extension

The generic mapping system must allow developers to author additional target tables without modifying Assam Core itself.

For example, an FPGA developer defining a custom instruction set should be able to write a target mapping JSON that directly states how Core operations map to that instruction set. Assam does not require that such a target be upstreamed or implemented as a dedicated built-in architecture module merely to use it.

Custom mappings are responsible for declaring their own target/profile identity and supported Core coverage. Unsupported Core operations are diagnosed explicitly rather than silently approximated.

## Requirements inherited from Bitlang Low lowering

Assam Core must be sufficient for a Bitlang Low backend to preserve:

- arbitrary semantic integer widths and signedness, either directly or through explicit lowering sequences;
- preserve `Int<Radix>x*` / `Uint<Radix>x*` as arbitrary-precision integers, lowering explicitly to dynamic limbs/runtime helpers where needed; do not substitute a fixed-width register, invented finite width, or truncation. Numeric `x0` is invalid, not an alias for `x*`. Reject `Float<Radix>x*` until its semantics are defined; never substitute a host float;
- distinguish zero-payload semantic validity from physical storage size. A zero-length array has zero elements; an array of N zero-payload elements retains N logical elements and normal bounds checks. Do not substitute physical address arithmetic for logical indexing when stride is zero. Preserve observable identity/Ref/borrow/lifetime rules, do not assume heap allocation or unique physical addresses, and keep any required descriptor/helper explicit;
- checked overflow behavior;
- deterministic logical/arithmetic shifts with validated shift counts;
- comparisons and explicit conditional/unconditional branches;
- function calls/returns and an explicit calling convention;
- byte-addressable or otherwise precisely specified memory access;
- bounds/check/trap sequences;
- deterministic load/store widths and endianness;
- explicit helper calls when a semantic operation cannot be represented by one instruction.

Bitlang ownership, borrow, Ref, cleanup, class, and closure semantics should already be validated/lowered before Core. Core executes the resulting explicit operations and control flow; it does not reimplement those high-level analyses.

These type semantics are inherited rather than redefined by Assam. See Bitlang Low's [numeric types](https://github.com/tomiya7688/Bitlang_low/blob/main/docs/numeric-types.md), [language specification](https://github.com/tomiya7688/Bitlang_low/blob/main/docs/language-spec.md), [exact layout](https://github.com/tomiya7688/Bitlang_low/blob/main/docs/exact-layout.md), and [runtime-helper ABI](https://github.com/tomiya7688/Bitlang_low/blob/main/docs/runtime-helper-abi.md). These requirements constrain backend lowering and explicit ABIs; they do not add Core opcodes.

## Syntax baseline

The existing ASSAM text form remains the starting point:

- labels identify branch/call targets;
- instructions contain an opcode followed by explicit operands;
- registers, immediates, and symbols are lexically distinguishable;
- comments and whitespace are non-semantic;
- one canonical spelling should be emitted by generators even if the parser accepts compatible aliases.

The exact grammar, operand kinds, opcode set, profile/version marker, and error rules are to be formalized before the profile is considered stable.

In the Python reference implementation, the `core` validation profile excludes the VM-only `Push` / `Pop` conveniences and high-level terminal operations. The versioned JSON registry at `assam/data/instruction_registry.json` is the shared source for opcode aliases, operand roles, execution-handler identifiers, explicit register operand reads/writes, guest-addressable data-memory read/write effects, integer-parameter positions, instruction-local trap conditions, target mapping hook IDs, and control-flow categories; the parser, C translator, VM, and analyzer consume it. The v2 shape is described by `assam/data/instruction-registry-v2.schema.json`. Each Core opcode has a namespaced `target_mapping_id` for future declarative mapping tables. These IDs do not imply that mappings exist or that target coverage is complete. Guest data-memory effects are distinct from VM-internal stacks and terminal-bus effects. Integer width and signedness are explicitly marked `not_decided`; this records the unresolved requirement and does not establish execution semantics. Trap conditions record behavior observed in the current Python reference VM, not normative Draft Core behavior; host/environment failures are excluded. Its schema version does not make the Core semantics stable: the profile remains Draft until its operand semantics, ABI, and target mappings are specified and validated.

JSON IR may carry an optional `profile` marker containing the selected profile name, profile version, and instruction-registry schema version. `assam json --profile core` validates and adds this marker. The JSON contract is defined by `assam/data/program-ir-v1.schema.json`, and the standalone marker schema is `assam/data/assam-core-profile-draft.schema.json`. Legacy JSON without a marker remains valid and defaults to Full. The current Core version is explicitly `draft`; this marker is for compatibility signaling, not a stability claim.

## Architecture translation acceptance criteria

Assam Core is not considered stable until:

- x64 mapping JSON exists and passes translation fixtures;
- ARM64 mapping JSON exists and passes translation fixtures;
- RISC-V mapping JSON exists and passes translation fixtures;
- every ordinary Core opcode has required mapping coverage for all three architectures or is explicitly classified as a runtime/VM ABI primitive;
- CI/schema validation rejects an uncovered ordinary Core opcode;
- representative programs produce semantically equivalent results in the reference VM and translated target executions/tests where the target test environment is available.

## Compatibility rule

A valid Assam Core program must also be a valid ASSAM program of the corresponding language version.

The reverse is not required: a full ASSAM program may use features that are intentionally unavailable to Bitlang VM.
