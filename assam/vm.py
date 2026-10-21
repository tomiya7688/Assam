"""Reference interpreter for Assam Core and full ASSAM profiles."""
from __future__ import annotations

import operator

from .instruction_set import InstructionSet
from .terminal import BasicTerminal, TerminalBus
from .terminal_error import TerminalOperationError


class VMError(RuntimeError):
    """Raised when an ASSAM instruction fails during execution."""


class VM:
    def __init__(self, program, *, register_count=16, profile=None):
        self.instruction_set = InstructionSet(register_count)
        profile = self.instruction_set.resolve_profile(program, profile)
        self.instruction_set.validate(program, profile=profile)
        self.program = program
        self.registers = {f"r{i}": 0 for i in range(register_count)}
        self.memory = {}
        self.stack = []
        self.call_stack = []
        self.bus = TerminalBus()
        self.profile = profile
        self.ip = 0
        self.halted = False
        self._handlers = {
            "move": self._op_move,
            "load": self._op_load,
            "store": self._op_store,
            "binary": self._op_binary,
            "unary": self._op_unary,
            "compare": self._op_compare,
            "jump": self._op_jump,
            "conditional": self._op_conditional,
            "call": self._op_call,
            "return": self._op_return,
            "halt": self._op_halt,
            "push": self._op_push,
            "pop": self._op_pop,
            "create_terminal": self._op_create_terminal,
            "destroy_terminal": self._op_destroy_terminal,
            "connect_terminal": self._op_connect_terminal,
            "disconnect_terminal": self._op_disconnect_terminal,
            "send": self._op_send,
            "broadcast": self._op_broadcast,
        }
        self._binary_operations = {
            "add": operator.add,
            "subtract": operator.sub,
            "multiply": operator.mul,
            "divide": self._divide,
            "modulo": self._modulo,
            "and": operator.and_,
            "or": operator.or_,
            "xor": operator.xor,
            "shiftleft": operator.lshift,
            "shiftright": operator.rshift,
        }

    def _value(self, operand):
        return self.registers[operand] if isinstance(operand, str) and operand in self.registers else operand

    def _reg(self, operand):
        if not isinstance(operand, str) or operand not in self.registers:
            raise VMError(f"invalid register: {operand!r}")
        return operand

    def _target(self, operand):
        if isinstance(operand, str) and operand in self.program.labels:
            return self.program.labels[operand]
        if isinstance(operand, int):
            return operand
        raise VMError(f"invalid jump target: {operand!r}")

    def step(self):
        if self.halted:
            return
        if not 0 <= self.ip < len(self.program.instructions):
            raise VMError(f"instruction pointer out of range: {self.ip}")
        instruction = self.program.instructions[self.ip]
        definition = self.instruction_set.definition(instruction.opcode)
        try:
            handler = self._handlers[definition["handler"]]
            next_ip = handler(definition, instruction.operands)
        except VMError as exc:
            raise VMError(f"{exc} at instruction {self.ip}: {instruction}") from exc
        except TerminalOperationError as exc:
            line = f" (line {instruction.source_line})" if instruction.source_line is not None else ""
            raise VMError(f"terminal error at instruction {self.ip}{line}: {instruction.opcode}: {exc}") from exc
        except (IndexError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise VMError(f"execution error at instruction {self.ip}: {instruction}: {exc}") from exc
        if next_ip is not None:
            self.ip = next_ip
        elif not self.halted:
            self.ip += 1

    def run(self, *, max_steps=100000):
        if type(max_steps) is not int or max_steps < 0:
            raise ValueError("max_steps must be a non-negative integer")
        for _ in range(max_steps):
            if self.halted:
                return dict(self.registers)
            self.step()
        if self.halted:
            return dict(self.registers)
        raise VMError(f"step limit exceeded: {max_steps}")

    def _op_move(self, definition, args):
        self.registers[self._reg(args[0])] = self._value(args[1])

    def _op_load(self, definition, args):
        self.registers[self._reg(args[0])] = self.memory.get(self._value(args[1]), 0)

    def _op_store(self, definition, args):
        self.memory[self._value(args[0])] = self._value(args[1])

    def _op_binary(self, definition, args):
        destination = self._reg(args[0])
        left, right = self._value(args[1]), self._value(args[2])
        operation = definition["operation"]
        self.registers[destination] = self._binary_operations[operation](left, right)

    def _op_unary(self, definition, args):
        self.registers[self._reg(args[0])] = operator.invert(self._value(args[1]))

    def _op_compare(self, definition, args):
        self.registers[self._reg(args[0])] = int(self._value(args[1]) == self._value(args[2]))

    def _op_jump(self, definition, args):
        return self._target(args[0])

    def _op_conditional(self, definition, args):
        left, right = self._value(args[1]), self._value(args[2])
        predicates = {"equal": operator.eq, "not_equal": operator.ne}
        if predicates[definition["predicate"]](left, right):
            return self._target(args[0])

    def _op_call(self, definition, args):
        target = self._target(args[0])
        self.call_stack.append(self.ip + 1)
        return target

    def _op_return(self, definition, args):
        if not self.call_stack:
            raise VMError("call stack underflow")
        return self.call_stack.pop()

    def _op_halt(self, definition, args):
        self.halted = True

    def _op_push(self, definition, args):
        self.stack.append(self._value(args[0]))

    def _op_pop(self, definition, args):
        if not self.stack:
            raise VMError("stack underflow")
        self.registers[self._reg(args[0])] = self.stack.pop()

    def _op_create_terminal(self, definition, args):
        self.bus.register(BasicTerminal(self._value(args[0])))

    def _op_destroy_terminal(self, definition, args):
        self.bus.unregister(self._value(args[0]))

    def _op_connect_terminal(self, definition, args):
        self.bus.connect(self._value(args[0]), self._value(args[1]))

    def _op_disconnect_terminal(self, definition, args):
        self.bus.disconnect(self._value(args[0]), self._value(args[1]))

    def _op_send(self, definition, args):
        self.bus.send(self._value(args[0]), self._value(args[1]), self._value(args[2]))

    def _op_broadcast(self, definition, args):
        self.bus.broadcast(self._value(args[0]), self._value(args[1]))

    @staticmethod
    def _divide(left, right):
        quotient = abs(left) // abs(right)
        return -quotient if (left < 0) != (right < 0) else quotient

    @classmethod
    def _modulo(cls, left, right):
        return left - cls._divide(left, right) * right
