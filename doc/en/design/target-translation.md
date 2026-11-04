# Target Translation

Language: [日本語](../../jp/設計/ターゲット変換.md) | English

Target Issues: #4 (x64/ARM64/RISC-V), #5 (Wasm), #6 (JVM), #2 (mapping gate). Decisions: DEC-12, DEC-13, DEC-15, PRO-10.

## 1. Separation of Responsibilities

```text
Core program (IR)
   -> [loader]        load mapping JSON (versioned) and check against the registry
   -> [expander]      Core instruction -> target instruction template sequence (symbolic)
   -> [allocator]     assign scratch / target registers (within declared ranges)
   -> [encoder boundary]   symbolic instruction -> machine code / assembly string (target-specific, separate responsibility)
   -> [linker/ABI]    labels, relocations, helper symbols (target-specific, separate responsibility)
```

- The loader/expander are **target-independent** and follow only what the mapping table declares. Target-specific code is confined to the encoder boundary and the ABI adapter.
- Do not embed a general-purpose programming language in the mapping table. If a complex semantic lowering is needed, decompose Core instead (#4).
- The translator does not reconstruct source-level semantics of Bitlang Low (ownership, etc.).

## 2. Mapping Table schema v2 (PRO-10)

The current v1 carries only the shape of instruction sequences (opcode and operand references). v2 adds semantics-affecting information declaratively.

```jsonc
{
  "schema_version": 2,
  "core_profile": { "name": "core", "version": "1" },
  "registry_schema_version": 3,
  "target": { "architecture": "riscv64", "profile": "rv64gc" },
  "resources": {
    "scratch": ["t0", "t1"], // target registers the translation may use freely
    "reserved": ["sp", "gp", "tp"], // not used for Core register allocation
    "register_map": { "r1": "x10", "r2": "x11" }, // Core r1..r31 -> target registers (r0 is constant 0)
  },
  "mappings": [
    {
      "target_mapping_id": "assam.core.1.add",
      "variants": [
        {
          "when": {},
          "sequence": [
            {
              "opcode": "add",
              "operands": [
                { "kind": "core_reg", "index": 0 },
                { "kind": "core_reg", "index": 1 },
                { "kind": "core_reg", "index": 2 },
              ],
            },
          ],
        },
      ],
    },
    {
      "target_mapping_id": "assam.core.1.divs",
      "variants": [
        {
          "when": {},
          "sequence": [
            /* a sequence making MIN/-1 and division by zero explicit, or abi_helper */
          ],
        },
      ],
    },
  ],
}
```

Added expressions (not in v1):

| Expression                                                | Purpose                                                                                                                             |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `register_map` / `reserved` / `scratch`                   | Assignment of Core r0-r31 to target registers, and temporary resources. r0 is pinned to the zero register or expanded to constant 0 |
| operand references `core_reg` / `core_imm` / `core_label` | Distinguish the kind of Core operand (the current `core_operand` is positional only)                                                |
| `condition`                                               | Map of branch conditions to target condition codes/instructions (`eq`, `ne`, `lt`, `ge`, `ltu`, `geu`)                              |
| `variants[].when`                                         | Case split by immediate range or operand identity (e.g. `rd==rs1`). Conditions are declarative comparisons only (range, equality)   |
| `abi_helper`                                              | Call to a target ABI helper symbol (`assam_helper_<id>`, trap-report helper)                                                        |
| `trap_sequence`                                           | How a Core trap (div_by_zero, etc.) is represented on the target (declares a sequence that branches to the trap helper)             |
| `unsupported`                                             | Explicit marking of combinations that require prior Core decomposition                                                              |

Constraint: `when` takes only a finite set of predicates (`imm_fits_signed(bits)`, `same_register(a,b)`, etc.). No loops, recursion, or variables. The predicate set is fixed by the schema; additions go through a design PR.

## 3. Core admission gate (#4)

A PR that adds or changes an ordinary (`ordinary`) Core opcode must satisfy all of the following in the same PR.

1. x64 mapping, 2. ARM64 mapping, 3. RISC-V mapping, 4. mapping schema validation, 5. representative translation fixture (golden).

`abi_primitive` (e.g. `hcall`) is an exception that requires a classification and a helper/ABI mapping (DEC-12). CI mechanically verifies which opcodes are covered by all three tables and fails if any ordinary opcode is uncovered (the current coverage manifest/matrix check is reorganized around v1 instructions and v2 tables).

## 4. Check Tiers (clarifying the scope of semantic claims)

| Tier                     | Content                                                                                                  | Current status             | WP                |
| ------------------------ | -------------------------------------------------------------------------------------------------------- | -------------------------- | ----------------- |
| L1 Structure             | schema, registry references, duplicates, operand ranges                                                  | Implemented (Draft tables) | Continue          |
| L2 Coverage              | the three targets' `in_scope`/`out_of_scope` declarations match the tables                               | Implemented                | Reorganized in C3 |
| L3 Golden                | the expansion result (symbolic instruction sequence) of representative Core programs matches expectation | Not yet                    | C2/C3             |
| L4 Execution equivalence | execute the translation result on the target (or an emulator) and match the reference VM's observation   | Not yet                    | C4                |

CI/PR reports state the **name of the check tier**. Do not write "the translation is correct" on the basis of L1-L2 success. L4 needs an execution environment; if unavailable, state the environment and report it as not run.

### L4 execution environments

- RISC-V: `qemu-riscv64` (user mode). x64: native or qemu. ARM64: `qemu-aarch64`.
- In CI (GitHub Actions), run to the extent a runner/qemu for the architecture is available. If not, **skip the job and record the skip reason**, and write "L4 not reached" in the completion criteria.
- The comparison target for execution equivalence is the observation JSON (registers, memory, trap). The means of observing traps on the target (trap helper, signals) is defined by `trap_sequence` as part of the ABI adapter specification.

## 5. Migration of Bundled Mapping Tables

Replace the Draft tables in `examples/targets/` (x86-64 / AArch64 / RV64I, `*-draft`) with tables for `core` version `1`. During migration the old tables may be structurally checked in parallel in CI; delete the old tables once v1 coverage is complete. Table file names are `<arch>-<profile>-v1.{mapping,coverage}.json`.

Instructions that the current Draft tables mark `out_of_scope` (division, shifts, memory, etc.) are to be made `in_scope` in v1 through `variants`/`trap_sequence`/`abi_helper`. Known target-specific difficulties:

| Instruction       | Difficulty                                                                                              | Approach                                                                                                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `divs`/`rems`     | x86 `idiv` raises #DE on `MIN/-1`, and also on a zero divisor. ARM64 `sdiv` yields 0 for a zero divisor | Declare preceding compares/branches in `variants` to reproduce the result of PRO-03                                                        |
| `shl`/`shr`/`sar` | Shift amount fixed to cl (x86). Differing mask widths                                                   | Explicit 6-bit mask via `and`, or select BMI2 `shlx` via `profile`                                                                         |
| `mulhu`/`mulhs`   | x86 `mul`/`imul` are fixed to rdx:rax                                                                   | Declare a sequence that saves rax/rdx using scratch                                                                                        |
| `ld*`/`st*`       | Range check (memory bounds)                                                                             | Declare the target's memory model and the base+limit check of `memory_bytes` as a sequence                                                 |
| `jal`/`jr`        | Putting an index value into a register                                                                  | Define an ABI rule that turns instruction indices into a jump table or label-relative addresses (`jr` is an index -> address table lookup) |

For `jal`/`jr`, "instruction index = register value" is represented natively by an **index -> address table**. Generating this table is the responsibility of the linker/ABI adapter; the mapping table holds only the "table lookup" instruction sequence.

## 6. Custom / FPGA Targets (DEC-13)

- A developer writes `<arch>-<profile>-v1.mapping.json` and passes it to the generic translator, as in `assam translate --mapping my.json prog.s`. No change to Assam itself is needed.
- Core semantics are unchanged. Core instructions the table does not support get an **explicit diagnostic** (unsupported ones are never silently approximated, regardless of whether an `unsupported` declaration exists).
- Out of scope for first-party CI (three required targets). Promotion to official status adds dedicated L3/L4 fixtures and CI.
- Place a minimal example of "how to write a custom target table" (an FPGA example) in `docs` (WP-C5).

## 7. Wasm Translation (#5, Phase D)

```text
Core IR -> CFG normalization/structuring -> register->local/stack lowering -> Wasm instruction mapping -> module output
```

- Structured control flow: convert an arbitrary CFG to `block`/`loop`/`br`. For a reducible CFG use a standard algorithm (Relooper / Stackifier family); for an irreducible one fall back to `loop` + dispatch variable (generalization via a state variable). The output must be deterministic.
- Registers: r0-r31 become `i64` locals. `r0` is constant 0.
- Guest memory: map to the start of Wasm linear memory (`memory_bytes`), and make the memory range check explicit in the instruction sequence (even when using Wasm traps, define in the runtime how they correspond to Core's `memory_out_of_range`).
- Trap: represent a Core trap by `unreachable` plus a host trap notification, or by a return value. The scheme is fixed in a design PR (when D1 starts) and must be mappable to the observation JSON.
- `jal`/`jr`: represent as an indirect jump through an index table (`br_table`).
- Simple arithmetic and comparisons can reuse the JSON mapping foundation. No Wasm-specific Core instructions are added.
- Completion criteria: a representative Core program is translated to a valid Wasm module, the observation matches the reference VM, and the translation is deterministic (#5).

## 8. JVM Bytecode Translation (#6, Phase D)

```text
Core IR -> CFG normalization -> register->local lowering -> verifier/type-state adaptation -> JVM instruction mapping -> class/method output
```

- Registers: `long` locals. The operand stack is for JVM-side temporaries.
- Guest memory: do not make JVM objects raw addresses (DEC-15). Guest memory uses `byte[]` (or `ByteBuffer`/`MemorySegment`) as an explicit runtime representation, with range checks done in runtime helpers.
- Branch/jal/jr: `goto`/`if*` to labels. `jr` goes to the target index via `tableswitch`/`lookupswitch`. No nested method boundaries; a single method (if it grows too large, split the CFG and make frame state explicit).
- Verifier: generate stack map frames deterministically (hand-written, or a self-implemented equivalent of `ClassWriter`; policy is not to add external dependencies).
- Trap: even when using Java exceptions, fix the rule that maps to the observation JSON (exception kind -> trap kind).
- Completion criteria: a representative Core program becomes a classfile that passes the verifier, the observation on the JVM matches the reference VM, and the output is deterministic (#6).

## 9. Acceptance Criteria

- WP-C1: schema v2, loader, expander, encoder-boundary interface, unit tests.
- WP-C2: v1 tables for the three targets (up to L1/L2/L3).
- WP-C3: coverage CI for v1 instructions (CI fails on an uncovered ordinary opcode).
- WP-C4: L4 execution equivalence (to the extent the environment is available). If not reached, state the reason.
- WP-C5: custom target example and documentation.
