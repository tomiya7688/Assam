# Task-to-source map

Language: [日本語](../jp/作業別コンテキスト案内.md) | English

After the shared rules in `AGENTS.md`, use only the row relevant to this task. Paths below are relative to the repository root. Narrow candidates with `rg --files` / `rg -n`, then read the needed portions of the source and tests. English specifications link to their Japanese canonical versions. For unlisted work or a changed shared boundary, inspect affected consumers too.

| Work | First sources to inspect | Initial verification candidates |
| --- | --- | --- |
| Text syntax and JSON IR | `assam/parser.py`, `assam/ir.py`, `assam/generator.py`, `doc/en/instruction-set.md` | Relevant cases in `tests/test_ir_labels.py`, `tests/test_assam.py` |
| VM, debugger, terminal | `assam/vm.py`, `assam/debugger.py`, `assam/terminal.py`, `doc/en/instruction-set.md` | Relevant cases in `tests/test_step_budget.py`, `tests/test_arithmetic_zero.py`, `tests/test_terminal_diagnostics.py` |
| Core profile and registry | `assam/instruction_set.py`, `assam/profile.py`, `assam/data/instruction_registry.json`, `doc/en/assam-core.md` | Select tests using the changed opcode/profile with `rg -n`; check the matching schema when changing JSON |
| Target coverage and mappings | Target-specific `.agents/skills/assam-target-mappings/SKILL.md`, `assam/target_coverage.py`, `examples/targets/` | Relevant cases in `tests/test_target_mappings.py`, `tests/test_target_matrix.py`, `tests/test_shipped_target_mappings.py` |
| C input and static analysis | `assam/c_frontend.py`, `assam/analyzer.py`, `doc/en/c-input-translation.md`, `doc/en/developer-analysis-tools.md` | Relevant cases in `tests/test_c_frontend_analyzer.py` |

Only when changing the CLI boundary, search `assam/cli.py` and tests invoking that command. This map neither asks you to read every listed file nor limits the impact scope. Correct stale rows against current code. Usually skip unrelated logs, caches, and generated files; include them when the task or verification needs them.
