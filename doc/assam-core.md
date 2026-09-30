# Assam Core Profile

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
- checked overflow behavior;
- deterministic logical/arithmetic shifts with validated shift counts;
- comparisons and explicit conditional/unconditional branches;
- function calls/returns and an explicit calling convention;
- byte-addressable or otherwise precisely specified memory access;
- bounds/check/trap sequences;
- deterministic load/store widths and endianness;
- explicit helper calls when a semantic operation cannot be represented by one instruction.

Bitlang ownership, borrow, Ref, cleanup, class, and closure semantics should already be validated/lowered before Core. Core executes the resulting explicit operations and control flow; it does not reimplement those high-level analyses.

## Syntax baseline

The existing ASSAM text form remains the starting point:

- labels identify branch/call targets;
- instructions contain an opcode followed by explicit operands;
- registers, immediates, and symbols are lexically distinguishable;
- comments and whitespace are non-semantic;
- one canonical spelling should be emitted by generators even if the parser accepts compatible aliases.

The exact grammar, operand kinds, opcode set, profile/version marker, and error rules are to be formalized before the profile is considered stable.

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
