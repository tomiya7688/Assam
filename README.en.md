# ASSAM

Language: [日本語](README.md) | English

ASSAM (Assembly Abstract Machine) is the Python reference implementation of an intermediate representation and virtual execution platform.

The current implementation includes a text parser, JSON IR, basic VM, debugger, virtual terminal bus, a small C-input translator, and static analysis tools.

## Quick start

```python
from assam import VM, parse_program

program = parse_program("Move r0 2\nAdd r1 r0 3\nHalt")
print(VM(program).run()["r1"])
```

`VM.run(max_steps=N)` and `Debugger.continue_execution(max_steps=N)` limit instructions executed per call. Halting on instruction N succeeds. Reaching the limit while still running raises `VMError` in the VM or `RuntimeError` in the debugger. With `N=0`, a running program executes nothing and exceeds the limit, while an already halted one returns its state. Negative or non-integer values (including bool) raise `ValueError` before execution.

CLI commands, run from the repository root:

```text
python -m assam.cli run program.assam
python -m assam.cli run core-program.assam --profile core
python -m assam.cli json program.assam -o program.json
python -m assam.cli json core-program.assam --profile core -o core-program.json
python -m assam.cli run program.json --json
python -m assam.cli from-c examples/sum.c -o examples/sum.assam
python -m assam.cli analyze examples/sum.assam
```

`core` validates the strict Assam Core profile. The parser, VM, C translator, and analyzer share the [instruction registry](assam/data/instruction_registry.json). Registry schema v2 records register effects, guest-memory effects, trap conditions, and target mapping hook IDs. Draft mapping tables exist for x86-64, ARM64, and RV64I, but none prove executable translation or semantic equivalence. `check-target-matrix` can structurally check multiple `--mapping` tables against their coverage declarations. Integer width, signedness, and calling conventions remain undecided. Legacy JSON without a profile marker continues to mean Full.

JSON IR loading now rejects malformed label names and out-of-range or non-integer instruction indices with `ValueError` before execution. See the [instruction-set specification](doc/en/instruction-set.md).

In the Full profile, invalid terminal operations (unknown terminals, duplicate registration, or sending without a connection) raise `VMError` with the instruction index, source line when available, opcode, and reason. A rejected operation leaves terminal-bus state unchanged. Unexpected internal `KeyError` exceptions are not disguised as terminal operation errors.

`from-c` is not a full C compiler. It translates a small subset: integer locals and assignments, `+ - * / %`, parentheses, unary signs, and a final `return` inside `int main`. Branches, loops, function calls, pointers, and casts are unsupported. The return value is stored in VM register `r0`.

## Documentation

- [Japanese documentation](doc/jp/README.md)
- [English documentation](doc/en/README.md)
- [Assam Core profile](doc/en/assam-core.md)
- [Instruction set](doc/en/instruction-set.md)
- [C input translation](doc/en/c-input-translation.md)
- [Developer static analysis](doc/en/developer-analysis-tools.md)
