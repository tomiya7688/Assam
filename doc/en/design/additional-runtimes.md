# Additional Runtimes (Java VM / Rust VM)

Language: [日本語](../../jp/設計/追加実行系.md) | English

Target Issues: #14 (Java VM), #15 (Rust VM), #2 (role of implementation languages). Decisions: DEC-14, DEC-16. Status: Future (Phase D).

## 1. Positioning

| Implementation    | Role                                                                          | Comparison baseline |
| ----------------- | ----------------------------------------------------------------------------- | ------------------- |
| Go (Bitlang VM)   | Primary runtime                                                               | conformance corpus  |
| Python (ASSAM VM) | Reference implementation / baseline                                           | conformance corpus  |
| Java VM (#14)     | Independent additional runtime. Interprets and executes Core programs on Java | Same                |
| Rust VM (#15)     | Safety-focused native additional runtime                                      | Same                |

- Additional runtimes are **compatible implementations added alongside, not replacements for the Go primary runtime**. The canonical specification is the schema/registry and [Core semantics](core-semantics.md), not any language VM.
- The Java VM (#14) is **distinct from JVM bytecode translation (#6)**. The former interprets and executes Core programs; the latter translates Core into classfiles.
- Cross-platform support of the execution host and Core -> x64/ARM64/RISC-V translation (#4) are separate concerns, and both are maintained.

## 2. Definition of Ready

Do not start until all of the following are met (to avoid duplicate implementations and spec drift).

1. The Core v1 grammar, semantics, and registry v3 are settled, and the Python reference implementation conforms (WP-B1 to B4 complete).
2. The shared conformance corpus and the runtime protocol (`<impl> conformance-case`) are in place (WP-B5).
3. CI (#13) requires conformance, and all cases pass on the reference implementation.
4. The three-target translation (#4) is stable (through WP-C3). However, preparing the Java/Rust VMs is not a substitute for the required-target gate.

## 3. Common Design Constraints

- **Do not duplicate the registry/schema on the implementation side**. Load the registry JSON or use a generated artifact, and pin its sha256.
- **Do not adopt host-specific semantics**: do not expose Java numeric widths/exceptions/references, or Rust overflow/panic/pointers, as guest semantics. Wrap arithmetic explicitly (Rust: `wrapping_*`; Java: `long` wrapping plus `Long.divideUnsigned`/`Math.multiplyHigh` etc. for unsigned operations).
- **fail-closed**: reject unknown instructions, invalid operands, and inconsistent profiles before execution.
- **Do not add new high-level Core instructions**.
- I/O is the `conformance-case` protocol, a minimal CLI (`run`, `check`), and an execution API (library).

## 4. Java VM (#14)

- Location: a separate repository (or `runtimes/java/` in this repository; decided in a design PR at the start of work). Java version is the minimum LTS (fixed at the start of work).
- Structure: `Loader` (text/IR) -> `Validator` (registry) -> `Machine` (`long[32]`, `byte[] memory`, `pc`) -> `Observation`.
- Numerics: registers are `long`. Unsigned comparison, division, remainder, and high multiply use `Long.compareUnsigned`/`divideUnsigned`/`remainderUnsigned`/`Math.unsignedMultiplyHigh` (Java 18+).
- Memory: perform `byte[]` range checks ourselves, and do not leak `ArrayIndexOutOfBoundsException` as a guest trap.
- Completion criteria (#14): for the same version and same program, the observations of Go, Python, and Java match; Java passes all conformance cases; Java has no instruction definitions/semantics of its own.

## 5. Rust VM (#15)

- Location: a separate repository (or `runtimes/rust/`). Safe Rust in principle; `unsafe`/FFI boundaries and their necessity are documented and audited. Dependencies are minimal (serde-family is acceptable, with the reason recorded).
- Structure: `registry` (generated or JSON-loaded), `parser`, `program`, `machine`, `observe`.
- Numerics: `u64` with `wrapping_*`/`overflowing_*`; `i64` interprets signs via `as`. Do not make `panic` a guest behavior (rather than catching it with `catch_unwind`, the primary design goal is that no panic occurs; if one does, it is a host error).
- Cross-platform: run build + conformance in CI on Windows/Linux/macOS x x64/ARM64.
- Completion criteria (#15): the shared corpus can be executed, and the results, traps, and diagnostics of representative programs match the existing VMs.

## 6. Acceptance Criteria

- WP-D3 (Java) / WP-D4 (Rust) each first confirm in a PR that the Definition of Ready above is satisfied.
- Completion is judged by **all conformance cases passing** and **agreement in differential testing (Go/Python/this implementation)**. Items not run because external tools were unavailable must be stated.
