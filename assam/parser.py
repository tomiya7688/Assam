"""Parser for the small human-readable ASSAM syntax."""
from __future__ import annotations
import shlex
from .ir import Instruction, Program
class ParseError(ValueError): pass
def _operand(token):
    token=token.rstrip(",")
    if token.startswith("r") and token[1:].isdigit(): return token
    try: return int(token, 0)
    except ValueError: return token
def parse(line, *, line_number=None):
    line=line.split(";", 1)[0]
    try: tokens=shlex.split(line, comments=True, posix=True)
    except ValueError as exc: raise ParseError(f"line {line_number}: {exc}") from exc
    if not tokens: return ("",)
    if tokens[0].endswith(":") and len(tokens)==1:
        label=tokens[0][:-1]
        if not label: raise ParseError(f"line {line_number}: empty label")
        return (label,)
    return Instruction(tokens[0], tuple(_operand(x) for x in tokens[1:]), line_number)
def parse_program(source):
    instructions, labels=[], {}
    for number,line in enumerate(source.splitlines(),1):
        result=parse(line, line_number=number)
        if isinstance(result, tuple):
            if result[0]=="": continue
            if result[0] in labels: raise ParseError(f"line {number}: duplicate label {result[0]!r}")
            labels[result[0]]=len(instructions)
        else: instructions.append(result)
    return Program(instructions, labels)