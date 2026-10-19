"""Static summaries and control-flow analysis for ASSAM programs."""
from __future__ import annotations

from collections import Counter, deque

from .instruction_set import InstructionSet
from .ir import Program


class ProgramAnalyzer:
    """Produce deterministic instruction, register, and CFG summaries."""

    def __init__(self, register_count: int = 16) -> None:
        self.instruction_set = InstructionSet(register_count)

    def analyze(self, program: Program, *, profile: str | None = None) -> dict:
        """Validate and summarize a program without executing it."""
        profile = self.instruction_set.resolve_profile(program, profile)
        self.instruction_set.validate(program, profile=profile)
        count = len(program.instructions)
        opcode_counts: Counter[str] = Counter()
        reads: Counter[str] = Counter()
        writes: Counter[str] = Counter()
        data_memory_read_instructions = 0
        data_memory_write_instructions = 0

        for instruction in program.instructions:
            op = instruction.opcode.lower()
            definition = self.instruction_set.definition(op)
            opcode_counts[self.instruction_set.canonical_opcode(op)] += 1
            read_operands = definition["read_operands"]
            write_operands = definition["write_operands"]
            memory_effects = definition["data_memory_effects"]
            data_memory_read_instructions += int(memory_effects["read"])
            data_memory_write_instructions += int(memory_effects["write"])
            for index, operand in enumerate(instruction.operands):
                if not isinstance(operand, str) or not operand.startswith("r") or not operand[1:].isdigit():
                    continue
                if index in read_operands:
                    reads[operand] += 1
                if index in write_operands:
                    writes[operand] += 1

        leaders = self._leaders(program)
        blocks = self._blocks(program, leaders)
        block_by_instruction = {
            instruction_index: block_index
            for block_index, block in enumerate(blocks)
            for instruction_index in range(block["start"], block["end"] + 1)
        }
        for block in blocks:
            terminal_index = block["end"]
            terminal = program.instructions[terminal_index]
            block["successors"] = sorted({
                block_by_instruction[target]
                for target in self._successor_instructions(program, terminal_index, terminal)
                if target in block_by_instruction
            })

        reachable_blocks = self._reachable_blocks(blocks)
        unreachable = [
            instruction_index
            for block_index, block in enumerate(blocks)
            if block_index not in reachable_blocks
            for instruction_index in range(block["start"], block["end"] + 1)
        ]
        edges = [
            {"from": block_index, "to": target}
            for block_index, block in enumerate(blocks)
            for target in block["successors"]
        ]
        return {
            "profile": profile,
            "instruction_count": count,
            "opcode_counts": dict(sorted(opcode_counts.items())),
            "register_reads": dict(sorted(reads.items())),
            "register_writes": dict(sorted(writes.items())),
            "data_memory_read_instructions": data_memory_read_instructions,
            "data_memory_write_instructions": data_memory_write_instructions,
            "labels": dict(sorted(program.labels.items())),
            "basic_blocks": blocks,
            "control_flow_edges": edges,
            "reachable_blocks": sorted(reachable_blocks),
            "unreachable_instructions": unreachable,
        }

    def format_text(self, report: dict) -> str:
        """Format an analysis report for a terminal."""
        lines = [f"Instructions: {report['instruction_count']}", "Opcodes:"]
        if report["opcode_counts"]:
            lines.extend(f"  {name}: {count}" for name, count in report["opcode_counts"].items())
        else:
            lines.append("  (none)")
        lines.append("Register reads: " + self._format_registers(report["register_reads"]))
        lines.append("Register writes: " + self._format_registers(report["register_writes"]))
        lines.append(f"Data-memory read instructions: {report['data_memory_read_instructions']}")
        lines.append(f"Data-memory write instructions: {report['data_memory_write_instructions']}")
        lines.append(f"Basic blocks: {len(report['basic_blocks'])}")
        lines.append("Control-flow edges: " + (", ".join(f"B{edge['from']}->B{edge['to']}" for edge in report["control_flow_edges"]) or "(none)"))
        lines.append("Unreachable instructions: " + (", ".join(map(str, report["unreachable_instructions"])) or "(none)"))
        return "\n".join(lines)

    def _leaders(self, program: Program) -> list[int]:
        count = len(program.instructions)
        if count == 0:
            return []
        leaders = {0}
        for index, instruction in enumerate(program.instructions):
            definition = self.instruction_set.definition(instruction.opcode)
            flow = definition["flow"]
            if flow in {"jump", "conditional", "call"}:
                target = instruction.operands[0]
                leaders.add(program.labels[target] if isinstance(target, str) else target)
            if flow in {"jump", "conditional", "call", "return", "halt"}:
                if index + 1 < count:
                    leaders.add(index + 1)
        return sorted(leaders)

    def _blocks(self, program: Program, leaders: list[int]) -> list[dict]:
        blocks = []
        for block_index, start in enumerate(leaders):
            end = leaders[block_index + 1] - 1 if block_index + 1 < len(leaders) else len(program.instructions) - 1
            blocks.append({"id": block_index, "start": start, "end": end, "successors": []})
        return blocks

    def _successor_instructions(self, program: Program, index: int, instruction) -> list[int]:
        flow = self.instruction_set.definition(instruction.opcode)["flow"]
        count = len(program.instructions)
        if flow in {"halt", "return"}:
            return []
        if flow == "jump":
            target = instruction.operands[0]
            return [program.labels[target] if isinstance(target, str) else target]
        if flow in {"conditional", "call"}:
            target = instruction.operands[0]
            result = [program.labels[target] if isinstance(target, str) else target]
            if index + 1 < count:
                result.append(index + 1)
            return result
        return [index + 1] if index + 1 < count else []

    def _reachable_blocks(self, blocks: list[dict]) -> set[int]:
        if not blocks:
            return set()
        reached = {0}
        pending = deque([0])
        while pending:
            current = pending.popleft()
            for successor in blocks[current]["successors"]:
                if successor not in reached:
                    reached.add(successor)
                    pending.append(successor)
        return reached

    def _format_registers(self, registers: dict[str, int]) -> str:
        return ", ".join(f"{name}({count})" for name, count in registers.items()) or "(none)"
