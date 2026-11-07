# Core semantics (Core v1)

Language: [日本語](../../jp/設計/Core意味論.md) | English

Target issues: #3 (execution semantics of the Core ISA), connected to #2 and #4. Decisions: DEC-02 to DEC-09, DEC-14, PRO-01 to PRO-09.

> Classification: "Confirmed" means stated in the consumer contract of Issue #3; "Proposed" means decided by this design. The former Q1 (`mulhu`/`mulhs`) is decided in PRO-16.

## 1. Machine model

| Item         | Definition                                                                                                                              | Classification                |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| Registers    | `r0`-`r31`, 64 bits each. Initial value 0. `r0` always reads as 0; writes are discarded                                                 | Confirmed                     |
| PC           | Instruction index (0-based). Normally `+1`; only branch instructions change it                                                          | Proposed                      |
| Integers     | Values are 64-bit unsigned bit strings. Signed instructions interpret them as two's complement. Add, subtract, multiply are modulo 2^64 | Confirmed                     |
| Memory       | Independent byte-addressed space of size `memory_bytes` (instance parameter), zero-initialized, contiguous                              | Confirmed + Proposed (PRO-08) |
| Address      | 64-bit. Effective address `ea = (rbase + sext(off)) mod 2^64`                                                                           | Confirmed + Proposed          |
| Endianness   | Little-endian. Unaligned access allowed                                                                                                 | Confirmed                     |
| Hidden state | None. No call stack, flags, or implicit link register                                                                                   | Confirmed                     |
| Termination  | `halt` or an unhandled trap. No implicit stop past the end of the instruction sequence                                                  | Proposed                      |

One execution step: execute the instruction, then (if it did not trap) update PC. **A trapping instruction leaves no side effects** (registers, memory, and PC are not updated; however, the observed result includes the PC that trapped).

### 1.1 Check order, atomicity, and supplementary rules (review feedback)

- **Check, then commit**: each instruction first decides traps, then commits side effects. `st*` checks the whole range `[ea, ea+w)` before writing and never writes part of it and then traps. The effective address `ea` is `rbase + sext(off)` computed modulo 2^64, and wrap-around of that addition does not itself trap (e.g. `rbase = 2^64-1`, `off = 1` gives `ea = 0`). Then compare the range after detecting wrap-around of `ea + w` (`ea > memory_bytes - w`; `w > memory_bytes` is out of range). `jr` updates the PC after checking its target. Target labels of `jal`/branches are verified at load, so they never trap at run time.
- **Link value of `jal`**: a `jal` in the last instruction writes the instruction count, which is not a valid instruction index. Returning to it with `jr` is an `invalid_jump_target` trap (same as running past the end). Only indexes in `[0, instruction count)` are valid function-pointer values; mapping an index to a native address is done by the translator's index-to-address table ([target translation](target-translation.md)).
- **`hcall`**: an unregistered id traps `unknown_helper` with no side effects. If a registered helper can fail, its trap kind and state are defined by the helper ABI table (on the Bitlang Low side); Assam defines no standard helper in v1. A helper changes no register other than the result registers `r1`-`r2`, and memory side effects are limited to what the helper ABI table allows.
- **Immediate ranges**: `const` is `[-2^63, 2^64-1]` (any 64-bit value can be expressed; `0x` up to 16 digits, `-0x..` allowed), `off` is `[-2^31, 2^31-1]`, `trap`/`hcall` are `[0, 2^32-1]`. Out-of-range values are rejected at load with `core.syntax.immediate_range`.
- **`memory.segments`**: each segment satisfies `offset + length <= memory_bytes` and segments do not overlap. Violations are rejected before execution with `core.load.segment_out_of_range` / `core.load.segment_overlap` (not run-time traps).
- **Stack and calling convention are outside Core**: Core defines no stack region, SP, or caller/callee-saved convention (`r1`-`r31` are general purpose). The Bitlang backend reserves a region inside `memory_bytes` and initializes SP with `const` at entry. Conformance contains only corpora that do not depend on this convention.

## 2. Instruction list

Notation: `rd` = destination register, `rs` = source register, `imm` = immediate, `L` = label. Value symbols: `u` = unsigned 64-bit, `s` = signed 64-bit.

### 2.1 Data movement

| Instruction | Form            | Meaning                                                 |
| ----------- | --------------- | ------------------------------------------------------- |
| `const`     | `const rd, imm` | `rd = imm mod 2^64`. Allowed range is `[-2^63, 2^64-1]` |
| `mov`       | `mov rd, rs`    | `rd = rs`                                               |

### 2.2 Arithmetic and bitwise

| Instruction       | Form                 | Meaning                                                                                                                                                                                             |
| ----------------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `add` `sub` `mul` | `op rd, rs1, rs2`    | modulo 2^64                                                                                                                                                                                         |
| `mulhu`           | `mulhu rd, rs1, rs2` | Upper 64 bits of the unsigned 128-bit product (PRO-16)                                                                                                                         |
| `mulhs`           | `mulhs rd, rs1, rs2` | Upper 64 bits of the signed 128-bit product (PRO-16)                                                                                                                                                |
| `divu` `remu`     | `op rd, rs1, rs2`    | Unsigned quotient/remainder. `rs2==0` is a `div_by_zero` trap                                                                                                                                       |
| `divs` `rems`     | `op rd, rs1, rs2`    | Signed (quotient rounds toward zero; `rems = a - divs(a,b)*b`, so the remainder has the sign of the dividend). `rs2==0` is a `div_by_zero` trap. `MIN / -1 = MIN`, `MIN % -1 = 0` (no trap; PRO-03) |
| `and` `or` `xor`  | `op rd, rs1, rs2`    | Bitwise operations                                                                                                                                                                                  |
| `not`             | `not rd, rs`         | Bitwise inversion                                                                                                                                                                                   |
| `shl`             | `shl rd, rs1, rs2`   | Logical left. Shift amount is `rs2 & 63`                                                                                                                                                            |
| `shr`             | `shr rd, rs1, rs2`   | Logical right. Shift amount is `rs2 & 63`                                                                                                                                                           |
| `sar`             | `sar rd, rs1, rs2`   | Arithmetic right. Shift amount is `rs2 & 63`                                                                                                                                                        |

### 2.3 Comparison

| Instruction | Form                | Meaning                     |
| ----------- | ------------------- | --------------------------- |
| `seq`       | `seq rd, rs1, rs2`  | `rd = (rs1 == rs2) ? 1 : 0` |
| `slt`       | `slt rd, rs1, rs2`  | Signed `rs1 < rs2`          |
| `sltu`      | `sltu rd, rs1, rs2` | Unsigned `rs1 < rs2`        |

### 2.4 Memory

`ea = (rbase + sext(off)) mod 2^64`. `off` is a signed 32-bit value. If the access range `[ea, ea+w)` does not fit in `[0, memory_bytes)` (including wraparound of the addition), a `memory_out_of_range` trap occurs (reporting the address and width).

| Instruction                | Form                  | Meaning                                       |
| -------------------------- | --------------------- | --------------------------------------------- |
| `ld8u` `ld16u` `ld32u`     | `op rd, rbase, off`   | Zero-extend                                   |
| `ld8s` `ld16s` `ld32s`     | `op rd, rbase, off`   | Sign-extend                                   |
| `ld64`                     | `ld64 rd, rbase, off` | 64-bit                                        |
| `st8` `st16` `st32` `st64` | `op rs, rbase, off`   | Store the low w bits of `rs` in little-endian |

### 2.5 Control

| Instruction   | Form             | Meaning                                                                                                                                                                                                                                                 |
| ------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `jump`        | `jump L`         | `PC = L`                                                                                                                                                                                                                                                |
| `beq` `bne`   | `op rs1, rs2, L` | If equal/not equal, `PC = L`; if false, `PC+1`                                                                                                                                                                                                          |
| `blt` `bge`   | `op rs1, rs2, L` | Signed `<` / `>=`                                                                                                                                                                                                                                       |
| `bltu` `bgeu` | `op rs1, rs2, L` | Unsigned `<` / `>=`                                                                                                                                                                                                                                     |
| `brz` `brnz`  | `op rs, L`       | If `rs==0` / `rs!=0`, `PC = L`                                                                                                                                                                                                                          |
| `jal`         | `jal rd, L`      | `rd = PC+1` (index of the next instruction); `PC = L`. With `rd=r0` it is a plain jump. The instruction count written by a `jal` in the last instruction is not a valid index; returning to it with `jr` is an `invalid_jump_target` trap (section 1.1) |
| `jr`          | `jr rs`          | `PC = rs`. If `rs` is outside `[0, instruction count)`, an `invalid_jump_target` trap                                                                                                                                                                   |
| `halt`        | `halt`           | Normal stop                                                                                                                                                                                                                                             |
| `trap`        | `trap imm`       | An `explicit` trap. `imm` is in `[0, 2^32-1]`                                                                                                                                                                                                           |
| `hcall`       | `hcall imm`      | Runtime helper call (ABI primitive). See section 5                                                                                                                                                                                                      |

A function call is `jal r31, f` and the return is `jr r31` (r31 is a convention and is not special in the semantics). The calling convention (arguments, return values, callee-saved registers) is the ABI of the Bitlang Low backend and is not specified by Core.

The non-selected path of a branch has no side effects whatsoever (to prevent recurrence of the conditional-branch defect of #8; verified by conformance).

### 2.6 Static validation (at load)

Rejected before execution: unknown opcode, operand count/kind violation, register out of range, immediate out of range, undefined/duplicate label, `L` out of range, `off` out of range. Only the dynamic target of `jr` is a runtime trap.

## 3. Traps

| kind                  | Condition                                                                                 | Extra information  |
| --------------------- | ----------------------------------------------------------------------------------------- | ------------------ |
| `div_by_zero`         | Divisor is 0                                                                              | pc                 |
| `memory_out_of_range` | Access range is outside memory                                                            | pc, address, width |
| `invalid_jump_target` | The target of `jr` is out of range, or `PC` runs past the end of the instruction sequence | pc, target         |
| `unknown_helper`      | The `hcall` id is not registered                                                          | pc, id             |
| `explicit`            | `trap imm`                                                                                | pc, code           |

- **Environment limits are not traps**: step limit, memory allocation failure, I/O failure, etc. (reported as a separate `limit` result).
- Observed result (PRO-07): `{"status":"halted"|"trapped"|"limit", "trap":{"kind","pc",...}, "registers":[32 u64 values (decimal strings)], "memory_sha256":"..."}`. Registers are decimal strings (to avoid the 53-bit precision problem of JSON). Comparison across implementations is done in this form.
- Adding or changing a trap kind is a compatibility contract. A change bumps the registry version.

## 4. Mapping the requirements from Bitlang Low

Core satisfies the following through lowering, **without adding them as instructions** (DEC-09).

- **checked overflow**: For signed addition `c = a + b`, overflow is detected by testing `((a ^ c) & (b ^ c)) < 0` with `xor`/`and`/`slt`, and branching to `trap` if true. For signed multiplication overflow, use `mulhs` (PRO-16) and compare the upper 64 bits with the sign extension of the lower 64 bits; for unsigned 64-bit multiplication, branch to `trap` when the `mulhu` result is non-zero.
  Example (`c` is the sum): `add c, a, b` / `xor t1, a, c` / `xor t2, b, c` / `and t1, t1, t2` / `slt t1, t1, r0` / `brnz t1, overflow`.
- **Arbitrary semantic widths** (8/16/32 bit, etc.): after a 64-bit operation, sign/zero-extend with `shl` + `sar`/`shr` to preserve the width.
- **Beyond 64 bits** (including x*): the backend lowers to a limb sequence (64-bit words), and carry/borrow is obtained with `sltu`. Example: 128-bit addition `(hi,lo)=(ah,al)+(bh,bl)` is `add lo`, `sltu c, lo, al`, `add hi`, `add hi, hi, c`.
  For three or more limbs, compute the carry of `a+b` and the carry of `+c_in` separately with `sltu`, combine them with `or`, and pass it to the next limb. `Int<Radix>x*`/`Uint<Radix>x*` are handled with dynamic limbs or a runtime helper (`hcall`), not substituted by a fixed width or truncation. The numeric type `x0`is invalid and is not an alias of`x*`. `Float<Radix>x\*` is rejected and is not substituted by a host float (Q5).
- **zero-payload**: distinguish the logical element count from the physical size. Even with stride 0, do not use address arithmetic in place of the logical index; make bounds checks explicit with compare + branch + `trap`. If identity/Ref/borrow/lifetime is observable, the backend keeps a descriptor explicitly. Core has no concept of arrays/references.
- **bounds/check/trap sequences**: a combination of `sltu` + `brz`/`brnz` + `trap`.
- **Shift-amount validation**: the contract uses the low 6 bits (DEC-04). Where out-of-range shifts should trap, the backend makes this explicit with `sltu` + `trap`.

Semantic validation and lowering of Bitlang's Ownership/borrow/Ref/cleanup/class/closure are completed before Core; Core does not re-analyze them.

## 5. `hcall` (helper-call, ABI primitive)

- `hcall imm`: calls runtime helper number `imm`. Arguments are `r1`-`r6`, results are `r1`-`r2`, and other registers are preserved (the range the helper may clobber is defined in the helper ABI table).
- The meaning of helper numbers follows the Bitlang Low [runtime-helper ABI](https://github.com/tomiya7688/Bitlang_low/blob/main/docs/runtime-helper-abi.md); Assam defines only the number space, the calling convention, and trap handling. **In v1 Assam defines no standard helpers of its own** (only registered numbers are valid). Conformance verifies both registered and unregistered cases.
- Translation: for x64/ARM64/RISC-V it expands to the `abi_helper` reference in the mapping table (a call to the symbol `assam_helper_<id>`). This is the "explicit exception for runtime/ABI primitives" of DEC-12 and is classified separately from three-target coverage of ordinary opcodes.

## 6. Mapping from Draft (current Core)

| Draft                    | v1                                                              | Notes                                                                    |
| ------------------------ | --------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `Move r, imm`            | `const rd, imm`                                                 | Immediate assignment                                                     |
| `Move r, r`              | `mov rd, rs`                                                    |                                                                          |
| `Add/Subtract/Multiply`  | `add/sub/mul`                                                   | Operands are registers only (PRO-02)                                     |
| `Divide/Modulo`          | `divs/rems` (matches Python's round-toward-zero) or `divu/remu` | Signedness must be chosen                                                |
| `And/Or/Xor/Not`         | `and/or/xor/not`                                                |                                                                          |
| `ShiftLeft/ShiftRight`   | `shl` / `shr` or `sar`                                          | The negative-shift trap disappears in v1; the amount uses the low 6 bits |
| `Compare r, a, b`        | `seq rd, rs1, rs2`                                              |                                                                          |
| `Load/Store`             | `ld64`/`st64` (choose a width)                                  | Sparse memory -> contiguous memory                                       |
| `Jump`                   | `jump`                                                          |                                                                          |
| `JumpEqual/JumpNotEqual` | `beq/bne`                                                       |                                                                          |
| `Call` / `Return`        | `jal r31, L` / `jr r31`                                         | The hidden call stack is removed                                         |
| `Halt`                   | `halt`                                                          |                                                                          |

The C frontend migrates to emit v1 canonical (WP-B6).

## 7. Acceptance criteria (WP-B4)

- The Python reference VM (`core` v1) implements all of the instructions and traps above and is verified by the corpus.
- Each instruction has at least: normal values, boundary values (0, 1, `-1`, `MIN`, `MAX`), a write to `r0`, trap paths, and no side effects (on trap) cases.
- Existing Full VM tests are unaffected (separate class).
- The observed JSON (section 3) is fixed as the expected values of the corpus.
