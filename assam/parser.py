"""Parser for the human-readable ASSAM syntax (Full profile text).

Tokens are separated by whitespace or commas. A ``;`` or ``#`` outside a
quoted string starts a comment. A double-quoted string is a ``StringLiteral``
whose content is kept as data, including ``;``, ``#``, digits and register
names. A bare word is a register (``r<N>``), an integer (decimal or ``0x``) or a
symbol.
"""

from __future__ import annotations

from .ir import Immediate, Instruction, Program, Register, StringLiteral, Symbol
from .instruction_set import InstructionSet

_instruction_set = InstructionSet()

_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r"}
_BARE_STOP = set(' \t\r\n,";#"')


class ParseError(ValueError):
    pass


def _tokenize(line, line_number):
    """Yield ``(is_string, text)`` pairs for one source line."""
    tokens = []
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch in " \t\r\n,":
            i += 1
        elif ch in ";#":
            break
        elif ch == '"':
            i, text = _quoted(line, i, line_number)
            if i < n and line[i] not in _BARE_STOP:
                raise ParseError(
                    f"line {line_number}: string literal must be followed by a separator"
                )
            tokens.append((True, text))
        else:
            start = i
            while i < n and line[i] not in _BARE_STOP:
                i += 1
            tokens.append((False, line[start:i]))
    return tokens


def _quoted(line, start, line_number):
    """Read a quoted string starting at ``start``; return (next index, value)."""
    out = []
    i = start + 1
    n = len(line)
    while True:
        if i >= n:
            raise ParseError(f"line {line_number}: unterminated string literal")
        ch = line[i]
        if ch == '"':
            return i + 1, "".join(out)
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= n:
            raise ParseError(
                f"line {line_number}: unterminated escape in string literal"
            )
        code = line[i + 1]
        if code == "x":
            digits = line[i + 2 : i + 4]
            if len(digits) != 2 or any(
                c not in "0123456789abcdefABCDEF" for c in digits
            ):
                raise ParseError(
                    f"line {line_number}: invalid \\x escape in string literal"
                )
            out.append(chr(int(digits, 16)))
            i += 4
        elif code in _ESCAPES:
            out.append(_ESCAPES[code])
            i += 2
        else:
            raise ParseError(
                f"line {line_number}: unknown escape \\{code} in string literal"
            )


def _bare_operand(text):
    if text[:1] == "r" and text[1:].isdigit() and text[1:] == str(int(text[1:])):
        return Register(int(text[1:]))
    try:
        return Immediate(int(text, 0))
    except ValueError:
        pass
    try:
        return Symbol(text)
    except ValueError as exc:
        raise ParseError(str(exc)) from exc


def parse(line, *, line_number=None):
    tokens = _tokenize(line, line_number)
    if not tokens:
        return ("",)
    is_string, head = tokens[0]
    if is_string:
        raise ParseError(f"line {line_number}: an opcode cannot be a string literal")
    if head.endswith(":") and len(tokens) == 1:
        label = head[:-1]
        if not label:
            raise ParseError(f"line {line_number}: empty label")
        return (label,)
    definition = _instruction_set.definition(head)
    opcode = definition["canonical_name"] if definition is not None else head
    operands = tuple(
        StringLiteral(text) if is_string else _bare_operand(text)
        for is_string, text in tokens[1:]
    )
    return Instruction(opcode, operands, line_number)


def parse_program(source):
    instructions, labels = [], {}
    for number, line in enumerate(source.splitlines(), 1):
        result = parse(line, line_number=number)
        if isinstance(result, tuple):
            if result[0] == "":
                continue
            if result[0] in labels:
                raise ParseError(f"line {number}: duplicate label {result[0]!r}")
            labels[result[0]] = len(instructions)
        else:
            instructions.append(result)
    return Program(instructions, labels)
