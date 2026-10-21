"""Regression tests for VM and debugger step-budget boundaries."""

from __future__ import annotations

import unittest

from assam import VM, parse_program
from assam.debugger import Debugger
from assam.vm import VMError


class StepBudgetTests(unittest.TestCase):
    def test_vm_halt_on_last_allowed_step_succeeds(self):
        for source, budget, expected in (("Halt", 1, 0), ("Move r0 42\nHalt", 2, 42)):
            with self.subTest(source=source):
                vm = VM(parse_program(source))
                self.assertEqual(vm.run(max_steps=budget)["r0"], expected)
                self.assertTrue(vm.halted)

    def test_vm_does_not_run_instruction_after_budget(self):
        vm = VM(parse_program("Move r0 42\nHalt"))
        with self.assertRaisesRegex(VMError, "step limit exceeded: 1"):
            vm.run(max_steps=1)
        self.assertEqual((vm.ip, vm.registers["r0"], vm.halted), (1, 42, False))
        self.assertEqual(vm.run(max_steps=1)["r0"], 42)

    def test_vm_infinite_loop_stops_at_exact_budget(self):
        vm = VM(parse_program("Jump 0"))
        with self.assertRaisesRegex(VMError, "step limit exceeded: 3"):
            vm.run(max_steps=3)
        self.assertEqual(vm.ip, 0)
        self.assertFalse(vm.halted)

    def test_vm_zero_budget_and_already_halted(self):
        vm = VM(parse_program("Halt"))
        with self.assertRaisesRegex(VMError, "step limit exceeded: 0"):
            vm.run(max_steps=0)
        self.assertFalse(vm.halted)
        vm.step()
        self.assertEqual(vm.run(max_steps=0)["r0"], 0)

    def test_debugger_uses_same_budget_boundary(self):
        debugger = Debugger(VM(parse_program("Move r0 42\nHalt")))
        with self.assertRaisesRegex(RuntimeError, "debug step limit exceeded: 1"):
            debugger.continue_execution(max_steps=1)
        self.assertEqual((debugger.vm.ip, debugger.vm.registers["r0"]), (1, 42))
        self.assertTrue(debugger.continue_execution(max_steps=1).halted)
        self.assertTrue(debugger.continue_execution(max_steps=0).halted)

    def test_debugger_zero_budget_does_not_execute(self):
        debugger = Debugger(VM(parse_program("Halt")))
        with self.assertRaisesRegex(RuntimeError, "debug step limit exceeded: 0"):
            debugger.continue_execution(max_steps=0)
        self.assertEqual(debugger.vm.ip, 0)
        self.assertFalse(debugger.vm.halted)

    def test_invalid_budgets_fail_before_execution(self):
        for budget in (-1, True, 1.5, "2"):
            with self.subTest(budget=budget):
                vm = VM(parse_program("Halt"))
                with self.assertRaisesRegex(ValueError, "max_steps must be a non-negative integer"):
                    vm.run(max_steps=budget)
                self.assertEqual(vm.ip, 0)
                debugger = Debugger(VM(parse_program("Halt")))
                with self.assertRaisesRegex(ValueError, "max_steps must be a non-negative integer"):
                    debugger.continue_execution(max_steps=budget)
                self.assertEqual(debugger.vm.ip, 0)


if __name__ == "__main__":
    unittest.main()
