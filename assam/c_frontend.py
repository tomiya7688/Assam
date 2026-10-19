"""Translate a deliberately small, documented subset of C into ASSAM."""
from __future__ import annotations

import re

from .ir import Instruction, Program
from .instruction_set import InstructionSet


class CTranslator:
    """Translate simple integer-only C ``main`` functions into ASSAM v1."""

    _main = re.compile(r"\bint\s+main\s*\(\s*(?:void)?\s*\)\s*\{")
    _identifier = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
    _token = re.compile(r"\s*(0[xX][0-9A-Fa-f]+|[0-9]+|[A-Za-z_][A-Za-z0-9_]*|[()+\-*/%])")
    _precedence = {"+": 10, "-": 10, "*": 20, "/": 20, "%": 20}
    _opcodes = {"+": "Add", "-": "Subtract", "*": "Multiply", "/": "Divide", "%": "Modulo"}

    def __init__(self) -> None:
        self._variables: dict[str, str] = {}
        self._temporaries: set[str] = set()
        self._instructions: list[Instruction] = []
        self._instruction_set = InstructionSet()

    def translate(self, source: str) -> Program:
        """Translate one ``int main()`` function or raise ValueError."""
        self._variables = {}
        self._temporaries = set()
        self._instructions = []
        clean_source = re.sub(r"/\*.*?\*/|//[^\r\n]*", "", source, flags=re.S)
        body = self._main_body(clean_source)
        statements = [item.strip() for item in body.split(";") if item.strip()]
        if not statements:
            raise ValueError("C main must contain a return statement")

        has_return = False
        for index, statement in enumerate(statements):
            if statement.startswith("return") and (len(statement) == 6 or statement[6].isspace()):
                if index != len(statements) - 1:
                    raise ValueError("return must be the final statement in the supported C subset")
                expression = self._parse_expression(statement[6:].strip())
                value, temporary = self._compile_expression(expression)
                self._instructions.append(Instruction("Move", ("r0", value)))
                self._release_temporary(value, temporary)
                self._instructions.append(Instruction("Halt"))
                has_return = True
                continue
            if has_return:
                raise ValueError("statements after return are not supported")
            self._translate_statement(statement)

        if not has_return:
            raise ValueError("C main must end with a return statement")
        program = Program(self._instructions)
        self._instruction_set.validate(program, profile="core")
        return program

    def to_source(self, program: Program) -> str:
        """Format the translated IR as readable ASSAM text."""
        lines = []
        labels_by_index: dict[int, list[str]] = {}
        for label, index in program.labels.items():
            labels_by_index.setdefault(index, []).append(label)
        for index, instruction in enumerate(program.instructions):
            lines.extend(f"{label}:" for label in labels_by_index.get(index, []))
            operands = " ".join(str(value) for value in instruction.operands)
            lines.append(instruction.opcode if not operands else f"{instruction.opcode} {operands}")
        lines.extend(f"{label}:" for label in labels_by_index.get(len(program.instructions), []))
        return "\n".join(lines) + "\n"

    def _main_body(self, source: str) -> str:
        match = self._main.search(source)
        if match is None:
            raise ValueError("expected an 'int main()' or 'int main(void)' function")
        depth = 1
        for index in range(match.end(), len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    if source[index + 1 :].strip():
                        raise ValueError("only one C main function is supported")
                    return source[match.end() : index]
        raise ValueError("C main function is missing a closing brace")

    def _translate_statement(self, statement: str) -> None:
        declaration = re.fullmatch(r"int\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s*=\s*(.+))?", statement, re.S)
        if declaration:
            name, source_expression = declaration.groups()
            if name in self._variables:
                raise ValueError(f"duplicate C variable: {name}")
            register = self._allocate_variable(name)
            if source_expression is None:
                self._instructions.append(Instruction("Move", (register, 0)))
            else:
                value, temporary = self._compile_expression(self._parse_expression(source_expression))
                self._instructions.append(Instruction("Move", (register, value)))
                self._release_temporary(value, temporary)
            return

        assignment = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", statement, re.S)
        if assignment:
            name, source_expression = assignment.groups()
            if name not in self._variables:
                raise ValueError(f"assignment to undeclared C variable: {name}")
            value, temporary = self._compile_expression(self._parse_expression(source_expression))
            self._instructions.append(Instruction("Move", (self._variables[name], value)))
            self._release_temporary(value, temporary)
            return

        raise ValueError(f"unsupported C statement: {statement}")

    def _parse_expression(self, expression: str):
        tokens = self._tokenize(expression)
        self._tokens = tokens
        self._token_index = 0
        node = self._parse_binary(0)
        if self._token_index != len(self._tokens):
            raise ValueError(f"unexpected token in C expression: {self._tokens[self._token_index]!r}")
        return node

    def _tokenize(self, expression: str) -> list[str]:
        tokens = []
        position = 0
        while position < len(expression):
            if not expression[position:].strip():
                break
            match = self._token.match(expression, position)
            if match is None:
                raise ValueError(f"unsupported character in C expression at offset {position}")
            tokens.append(match.group(1))
            position = match.end()
        if not tokens:
            raise ValueError("empty C expression")
        return tokens

    def _parse_binary(self, minimum_precedence: int):
        left = self._parse_primary()
        while self._token_index < len(self._tokens):
            operator = self._tokens[self._token_index]
            precedence = self._precedence.get(operator, -1)
            if precedence < minimum_precedence:
                break
            self._token_index += 1
            right = self._parse_binary(precedence + 1)
            left = (operator, left, right)
        return left

    def _parse_primary(self):
        if self._token_index >= len(self._tokens):
            raise ValueError("expected an operand in C expression")
        token = self._tokens[self._token_index]
        self._token_index += 1
        if token == "-":
            return ("negate", self._parse_primary())
        if token == "+":
            return self._parse_primary()
        if token == "(":
            expression = self._parse_binary(0)
            if self._token_index >= len(self._tokens) or self._tokens[self._token_index] != ")":
                raise ValueError("unclosed parenthesis in C expression")
            self._token_index += 1
            return expression
        if token == ")" or token in self._precedence:
            raise ValueError(f"expected an operand, got {token!r}")
        if token[0].isdigit():
            return int(token, 16 if token.lower().startswith("0x") else 10)
        if self._identifier.fullmatch(token):
            if token not in self._variables:
                raise ValueError(f"use of undeclared C variable: {token}")
            return token
        raise ValueError(f"unsupported C expression token: {token!r}")

    def _compile_expression(self, node) -> tuple[int | str, bool]:
        if isinstance(node, int):
            return node, False
        if isinstance(node, str):
            return self._variables[node], False
        if node[0] == "negate":
            value, temporary = self._compile_expression(node[1])
            destination = self._allocate_temporary()
            self._instructions.append(Instruction("Subtract", (destination, 0, value)))
            self._release_temporary(value, temporary)
            return destination, True

        operator, left_node, right_node = node
        left, left_temporary = self._compile_expression(left_node)
        right, right_temporary = self._compile_expression(right_node)
        destination = self._allocate_temporary()
        self._instructions.append(Instruction(self._opcodes[operator], (destination, left, right)))
        self._release_temporary(left, left_temporary)
        self._release_temporary(right, right_temporary)
        return destination, True

    def _allocate_variable(self, name: str) -> str:
        for index in range(1, 16):
            register = f"r{index}"
            if register not in self._variables.values():
                self._variables[name] = register
                return register
        raise ValueError("C subset supports at most 15 local integer variables")

    def _allocate_temporary(self) -> str:
        for index in range(1, 16):
            register = f"r{index}"
            if register not in self._variables.values() and register not in self._temporaries:
                self._temporaries.add(register)
                return register
        raise ValueError("C expression requires more temporary registers than ASSAM provides")

    def _release_temporary(self, value, is_temporary: bool) -> None:
        if is_temporary:
            self._temporaries.discard(value)
