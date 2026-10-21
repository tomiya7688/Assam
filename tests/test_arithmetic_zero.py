"""Regression tests for zero operands in reference VM arithmetic."""

from __future__ import annotations

import unittest

from assam import VM, VMError, parse_program


class ArithmeticZeroTests(unittest.TestCase):
    def test_add_subtract_multiply_accept_zero_right_operand(self):
        cases = (
            ("Add", 7, 0, 7),
            ("Subtract", 7, 0, 7),
            ("Multiply", 7, 0, 0),
            ("Add", -7, 0, -7),
            ("Subtract", -7, 0, -7),
            ("Multiply", -7, 0, 0),
            ("Add", 0, -3, -3),
            ("Subtract", 0, -3, 3),
            ("Multiply", 0, -3, 0),
        )
        for opcode, left, right, expected in cases:
            for use_register in (False, True):
                with self.subTest(opcode=opcode, left=left, right=right, register=use_register):
                    setup = f"Move r1 {right}\n" if use_register else ""
                    operand = "r1" if use_register else str(right)
                    vm = VM(parse_program(f"{setup}{opcode} r0 {left} {operand}\nHalt"))
                    self.assertEqual(vm.run()["r0"], expected)

    def test_divide_and_modulo_by_zero_remain_vm_errors(self):
        for opcode in ("Divide", "Modulo"):
            for use_register in (False, True):
                with self.subTest(opcode=opcode, register=use_register):
                    setup = "Move r1 0\n" if use_register else ""
                    operand = "r1" if use_register else "0"
                    vm = VM(parse_program(f"Move r0 99\n{setup}{opcode} r0 7 {operand}\nHalt"))
                    failing_ip = 2 if use_register else 1
                    for _ in range(failing_ip):
                        vm.step()
                    with self.assertRaises(VMError) as caught:
                        vm.step()
                    self.assertIn(f"instruction {failing_ip}", str(caught.exception))
                    self.assertEqual(vm.ip, failing_ip)
                    self.assertEqual(vm.registers["r0"], 99)
                    self.assertIsInstance(caught.exception.__cause__, ZeroDivisionError)


if __name__ == "__main__":
    unittest.main()
