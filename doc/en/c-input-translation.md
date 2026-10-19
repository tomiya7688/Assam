# Initial C Input Translation Specification

Language: [日本語](../jp/C入力変換仕様.md) | English

`assam.c_frontend.CTranslator` translates a small C subset to ASSAM without adding dependencies.

## Supported input

- One `int main()` or `int main(void)` function
- Local `int` declarations, initialized or uninitialized
- Assignment to declared variables
- Integer literals (decimal or hexadecimal), variables, and parentheses
- Unary `+` / `-` and binary `+` / `-` / `*` / `/` / `%`
- A final `return` statement with an integer expression
- `//` and `/* ... */` comments

Variables declared without an initializer are initialized to zero in ASSAM. The return value is placed in `r0`, and the translated program ends with `Halt`. To match C integer division, ASSAM `Divide` rounds toward zero, and `Modulo` has the same sign as the dividend.

## Unsupported syntax

Conditionals, loops, function calls, parameters, global variables, arrays, pointers, floating-point values, compound assignments, increment operators, and multiple declarators are unsupported. Unsupported syntax and references to undeclared variables are reported as `ValueError`.

## Usage

Run these commands from the repository root:

```text
python -m assam.cli from-c examples/sum.c -o examples/sum.assam
python -m assam.cli run examples/sum.assam
```
