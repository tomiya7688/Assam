"""Regression tests for guest terminal errors and VM diagnostics."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from assam import VM, VMError, parse_program
from assam.terminal import TerminalBus
from assam.terminal_error import TerminalOperationError


class TerminalDiagnosticsTests(unittest.TestCase):
    def test_invalid_guest_operations_leave_bus_unchanged(self):
        cases = (
            ("DestroyTerminal missing", "unknown terminal: missing"),
            ("CreateTerminal a\nConnectTerminal a missing", "unknown terminal: missing"),
            ("CreateTerminal a\nDisconnectTerminal a missing", "unknown terminal: missing"),
            ("CreateTerminal a\nSend a missing 7", "unknown terminal: missing"),
            ("CreateTerminal a\nCreateTerminal b\nSend a b 7", "terminals are not connected: a -> b"),
            (
                "CreateTerminal a\nCreateTerminal b\nConnectTerminal a b\n"
                "Send a b 1\nSend a missing 7",
                "unknown terminal: missing",
            ),
            ("Broadcast missing 7", "unknown terminal: missing"),
            ("CreateTerminal a\nCreateTerminal a", "terminal already registered: a"),
        )
        for source, reason in cases:
            with self.subTest(source=source):
                vm = VM(parse_program(source))
                failing_ip = len(vm.program.instructions) - 1
                for _ in range(failing_ip):
                    vm.step()
                before = (
                    dict(vm.bus.terminals),
                    {name: set(peers) for name, peers in vm.bus.connections.items()},
                    tuple(vm.bus.messages),
                    {name: tuple(terminal.inbox) for name, terminal in vm.bus.terminals.items()},
                )
                with self.assertRaises(VMError) as caught:
                    vm.step()
                message = str(caught.exception)
                self.assertIn(vm.program.instructions[failing_ip].opcode, message)
                self.assertIn(f"instruction {failing_ip}", message)
                self.assertIn(f"line {failing_ip + 1}", message)
                self.assertIn(reason, message)
                self.assertEqual(vm.ip, failing_ip)
                self.assertEqual(
                    (
                        vm.bus.terminals,
                        vm.bus.connections,
                        tuple(vm.bus.messages),
                        {name: tuple(terminal.inbox) for name, terminal in vm.bus.terminals.items()},
                    ),
                    before,
                )

    def test_bus_reports_expected_guest_errors_explicitly(self):
        bus = TerminalBus()
        with self.assertRaisesRegex(TerminalOperationError, "unknown terminal: missing"):
            bus.unregister("missing")
        self.assertEqual((bus.terminals, bus.connections, tuple(bus.messages)), ({}, {}, ()))

    def test_unexpected_key_error_is_not_treated_as_guest_error(self):
        vm = VM(parse_program("DestroyTerminal missing"))

        def raise_internal_error(_name):
            raise KeyError("internal bug")

        vm.bus.unregister = raise_internal_error
        with self.assertRaisesRegex(KeyError, "internal bug"):
            vm.step()

    def test_cli_reports_terminal_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.assam"
            path.write_text("; comment\nDestroyTerminal missing\nHalt\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "assam.cli", "run", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("assam: error:", result.stderr)
        self.assertIn("DestroyTerminal", result.stderr)
        self.assertIn("instruction 0", result.stderr)
        self.assertIn("line 2", result.stderr)
        self.assertIn("unknown terminal: missing", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
