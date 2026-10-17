# Core bootstrap: arithmetic/control-flow draft

Status: **experimental subset**, not an admitted/stable Core v1 ISA.
Profile: `assam-core/v1-draft.1` (explicit API/CLI argument, not a text directive).
Related: #1, #2, #3, #4, #13. The broader [Core design](assam-core.md) remains the target.

## Decision and repository boundary

Implement one executable slice before adding independent Java/Rust VMs. Assam owns
`core/registry.json`, the Go `core` parser/bootstrap library, canonical emission,
and shared fixtures. Bitlang VM may import `github.com/tomiya7688/Assam/core`
instead of duplicating the grammar. Integration into that repository is pending;
this change does not claim that its execution engine has already been implemented.

`tools/core_reference.py` is a development-only Python oracle using the same JSON
registry; it is deliberately separate from the legacy Full Python public API.
Each VM implements semantic effects independently. The registry holds opcode
spelling, operand kinds/order, effect identifiers and instruction-level trap
classes; it does not contain executable scripts. Canonical spelling and semantic
change require profile/corpus review together, not a private consumer opcode fork.

This slice is a proposal for review, not admission of new stable ordinary Core
instructions without target mappings. Both parsers reject `assam-core/v1`.
`experimental-subset` and the required three targets are checked in tests. Do not
promote the profile until the full #1–#4 contracts and architecture coverage gate
are implemented. JSON Schema, complete effect metadata, mapping coverage checking,
and automatic consumer code generation remain pending under #2/#4.

## Text and validation

Source is UTF-8, with LF or CRLF lines, ASCII spaces/tabs, and semicolon comments.
NUL and invalid UTF-8 are rejected, including in comments. One instruction or one
standalone label per line; opcode spelling is lowercase and case-sensitive, no
aliases. Operands are comma-separated. Labels match `[A-Za-z_][A-Za-z0-9_]*`.
Registers are exactly `r0`–`r31`; leading zeros such as `r01` are not accepted.

Immediate grammar is `-?(0x[0-9a-fA-F]+|[0-9]+)`; no plus, underscores, floating
point, quoted values, binary prefix or uppercase `0X`. Decimal leading zeros are
decimal, not octal. Immediate range is [-2^63, 2^64-1]; negative values are encoded
as two's-complement bit patterns. Negative magnitudes above 2^63 are rejected.

The complete program is validated before execution, even unreachable code.
Duplicate labels, undefined targets, labels at EOF (including unused ones), wrong
arity, invalid registers and unsupported opcodes are rejected. Several labels may
name the same existing instruction. Empty programs are rejected. `Program` has
private fields so Go consumers cannot inject unvalidated instructions.

Canonical output preserves label/order, drops comments and blank lines, emits
commas followed by one space, unsigned decimal immediates, and a final LF. The
canonical form is idempotent. Source locations naturally change on normalization;
execution behavior, but not original line numbers, must survive a roundtrip.

This bootstrap implementation limits BOTH input and canonical UTF-8 source to
1 MiB; normalization can expand a negative/hex immediate. These are documented
host resource limits, not a claim about an eventual architectural instruction
address limit. Program JSON input is not implemented; Full's JSON loader must
not be used as an unvalidated route into this Core execution path.

## Machine state and instruction semantics

Each Run starts with 32 zeroed 64-bit registers and PC=0. r0 reads zero; writes
are discarded, but source validation and traps still occur when destination is
r0. Arithmetic is modulo 2^64. `s(x)` denotes signed two's-complement decoding.
All binary instructions below use `rd, ra, rb` and read both sources before
writing the destination. No implicit flags, memory or call stack exists.

| Opcode | Operands | Effect |
|---|---|---|
| const | rd, immediate | Write the immediate bit pattern. |
| add / sub / mul | rd, ra, rb | Modular addition/subtraction/multiplication. |
| and / or / xor | rd, ra, rb | Bitwise operation. |
| shl / shr | rd, ra, rb | Logical shift by rb & 63. |
| sar | rd, ra, rb | Arithmetic right shift of s(ra) by rb & 63. |
| divu / remu | rd, ra, rb | Unsigned quotient/remainder. |
| divs / rems | rd, ra, rb | Signed quotient truncates toward zero; remainder is a-q*b. |
| eq / ltu / lts | rd, ra, rb | Equality / unsigned less-than / signed less-than; result is 0 or 1. |
| brz / brnz | ra, label | Branch on zero/nonzero; otherwise PC+1. |
| jump | label | Set PC to the label's instruction index. |
| halt | none | Stop successfully at the current PC. |
| trap | immediate | Stop with explicit guest trap code. |

Division/remainder by zero traps without modifying destination. Signed min-int
/-1 returns min-int (the wrapped quotient), and its remainder is zero. Go's
integer behavior and the Python oracle's explicit signed operations are checked
against shared boundary fixtures; Python floor-division semantics are not the
signed contract. Only the selected arithmetic effect is evaluated.

Normal instructions advance PC by one. Falling off code is `invalid_pc`, not
implicit halt. There are no guest filesystem/process/network operations.

## Execution budget, diagnostics and JSON output

Budget is a required uint64 API argument (CLI defaults to 10000; negative CLI
values are rejected). It bounds attempted instructions, including halt and trap.
Check order is budget, PC validity, then instruction attempt. Budget=0 returns
`step_limit` without execution. Halt on attempt N succeeds with budget=N; attempt
N+1 is never executed. If the last permitted instruction falls off the program,
the next iteration reports `step_limit` before checking the now-invalid PC.

Results contain status, PC, attempted steps, source line, code, and all registers.
Register values and explicit trap payloads use fixed-width hexadecimal strings
so a JSON consumer cannot silently lose 64-bit register precision. PC/steps/line
are integer counters; consumers must use an integer-capable JSON parser for large
budgets (a JavaScript consumer should use a suitably small budget or bigint-aware
parser). There is no promise that JSON number counters above 2^53 fit JS Number.

- `halted`: current halt PC/line; CLI exit 0.
- `trap`: `division_by_zero`, `invalid_pc`, or `explicit:0x...`; CLI exit 1.
- `step_limit`: execution resource limit, not a guest arithmetic trap; CLI exit 1.
- Invalid input/profile/file/flags: stderr diagnostic, no execution JSON, exit 2.
- Nil/zero-value Go Program: `invalid_program` without execution.
- Unknown compiled semantic effect: `internal_error`, never a successful result.

For PC/resource errors without a current instruction, line is 0. Instruction
traps include their source line. Trap attempts count as a step; invalid PC checks
do not. Each Run is fresh and deterministic, not a mutable resume/debugger API.

## Verification and next increments

Shared golden inputs cover each of the 22 registered opcodes, overflow, signed
division edge cases, r0 (including r0-targeted division traps), false/taken
branches, unresolved/duplicate/end labels, canonical spelling and step limits.
Python/Go compare the complete result for 100 seeded generated programs in
addition to the golden corpus. Go fuzzing checks successful parse/emit/execute
invariants under a bounded budget. Fuzzing is testing, not a safety proof.

Next increments, in dependency order:

1. Review opcode names/profile selection; extend machine-readable effect/schema
   validation and pin the consumer dependency in Bitlang-VM.
2. Add bounded byte-addressed memory, little-endian unaligned load/store,
   jump-and-link/indirect-jump and an explicit runtime-helper ABI, preserving #3.
3. Add x64/ARM64/RISC-V JSON mappings and a real required coverage gate before
   admitting a stable profile. Do not treat empty mappings as completed coverage.
4. Add the common validated program IR; extend the Python public Core API and
   consumer conformance; then implement Java and later consider Rust.

Legacy Full bugs #7–#12 remain separate work. Existing Full tests are retained;
passing those few tests is not evidence that the open audit bugs are fixed.
