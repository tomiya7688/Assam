# Developer Static Analysis Tool

Language: [日本語](../jp/開発者評価ツール.md) | English

`ProgramAnalyzer` validates and analyzes program structure without executing it. It accepts JSON IR or ASSAM text and reports instruction totals, per-opcode counts, register read/write counts, counts of instructions that read or write guest data memory, labels, basic blocks, control-flow edges, and unreachable instructions. Register effects come from operand positions declared in the registry's `read_operands` / `write_operands`; data-memory effects come from `data_memory_effects`. VM-internal stack operations and terminal-bus effects are not counted as guest data-memory accesses.

## CLI

Run these commands from the repository root:

```text
python -m assam.cli analyze program.assam
python -m assam.cli analyze program.json --ir-json --format json
python -m assam.cli analyze core-program.assam --profile core
```

Basic-block ranges include both endpoint instruction indices. Edges refer to block IDs. Conditional branches and `Call` record both the branch target and the next instruction as successors. `Return` and `Halt` have no static successor.

Because the analyzer does not track Call/Return runtime behavior or terminal side effects, its results are structural guidance, not execution guarantees.
