# ASSAM Roadmap

Language: [日本語](../jp/開発予定.md) | English

## Phase 1

- [x] Python package foundation
- [x] Text parser
- [x] JSON IR and generator
- [x] ASSAM VM
- [x] Debugger
- [x] Terminal ABI and message bus
- [ ] Formalize error behavior and instruction set (JSON IR label-table validation on load, VM/debugger execution-budget boundary, registry schema v2, register read/write and guest-memory effects, unresolved integer width/signedness, trap conditions, Core target hook IDs, target coverage and mapping schemas v1, Core operand-reference bounds checks, per-target and required-three-target declaration/mapping consistency checks, three-target draft examples, and manifest scaffold CLI are implemented; integrating Bitlang Low's defined x*/zero-payload semantics into Assam backends, executable target translation, dynamic-limb/runtime-helper ABI, descriptor/identity rules, and implementation validation remain)
- [x] C-to-ASSAM input translation (integer expressions and tests implemented)
- [x] Developer analysis tools (static analysis and tests implemented)

## Shared rules

- One class per file.
- Each class has one responsibility.
- Manage each feature and its tests as a focused unit.
- Remove completed items from this roadmap or mark them complete.
