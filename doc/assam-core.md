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
```

Because Bitlang Low is a primary producer, Core must be easy to generate deterministically and must not require a backend to synthesize human-oriented high-level ASSAM features.

## Core design rules

1. One instruction has one explicit low-level effect.
2. Control flow is explicit.
3. Memory effects are explicit.
4. Runtime failures use defined trap/error behavior rather than host-language accidents.
5. No implicit ownership, cleanup, allocation, dynamic dispatch, closure capture, or other high-level language behavior exists in Core.
6. Pseudo-instructions and convenience syntax may exist in full ASSAM only when they lower deterministically to Core.
7. Core instruction semantics are versioned and machine-readable.
8. Parsers and VMs should consume the same canonical instruction definition rather than maintaining unrelated opcode tables.
9. Target translators may map one Core operation to multiple target instructions when the target ISA cannot express the required semantics directly.

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

## Compatibility rule

A valid Assam Core program must also be a valid ASSAM program of the corresponding language version.

The reverse is not required: a full ASSAM program may use features that are intentionally unavailable to Bitlang VM.
