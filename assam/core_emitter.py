"""Core v1 canonical textへの正規化出力。"""

from __future__ import annotations

from .instruction_set import InstructionSet
from .ir import Immediate, Program, Register, Symbol


# {"責務": "ProgramをCore v1のcanonical textへ決定的に出力する", "処理": ["命令ごとにlabel行と命令行を並べる", "即値は10進で出力する"], "副作用": [], "エラー": ["Coreで表せないProgramはValueError"], "補足": "形式は1命令=`    opcode op1, op2`、label行は`name:`、末尾に改行1つ"}
class CoreEmitter:
    # {"責務": "Programをcanonical textにする", "処理": ["labelを命令位置ごとにまとめる(同位置は定義順)", "opcode・operand数・operand型をCore定義と照合", "label行と命令行を出力"], "引数": ["program: 出力するProgram"], "戻り値": ["canonical text(命令がなければ空文字列)"], "副作用": [], "エラー": ["未知opcode、operand不一致、string/範囲外registerなどでValueError"]}
    def emit(self, program: Program) -> str:
        definitions = InstructionSet().core_v1_definitions()
        by_index: dict[int, list[str]] = {}
        for name, index in program.labels.items():
            by_index.setdefault(index, []).append(name)
        lines: list[str] = []
        for index, instruction in enumerate(program.instructions):
            for name in by_index.get(index, []):
                lines.append(f"{name}:")
            definition = definitions.get(instruction.opcode)
            if definition is None:
                raise ValueError(f"not a Core v1 opcode: {instruction.opcode!r}")
            kinds = [operand["kind"] for operand in definition["operands"]]
            if len(kinds) != len(instruction.operands):
                raise ValueError(f"{instruction.opcode}: operand count mismatch")
            rendered = [
                self._render(operand, kind)
                for operand, kind in zip(instruction.operands, kinds)
            ]
            lines.append(
                "    " + instruction.opcode + (" " + ", ".join(rendered) if rendered else "")
            )
        return "".join(line + "\n" for line in lines)

    # {"責務": "1つのoperandを期待種別に従って文字列にする", "処理": ["registerは範囲を確認", "symbolは名前、それ以外は10進整数"], "引数": ["operand: 型付きoperand", "kind: registryの期待種別"], "戻り値": ["canonicalな文字列"], "副作用": [], "エラー": ["種別違反・範囲外でValueError"]}
    @staticmethod
    def _render(operand, kind: str) -> str:
        if kind == "register":
            if not isinstance(operand, Register) or operand.index >= 32:
                raise ValueError(f"expected register r0..r31, got {operand!r}")
            return operand.name
        if kind == "symbol":
            if not isinstance(operand, Symbol):
                raise ValueError(f"expected a label symbol, got {operand!r}")
            return operand.name
        if not isinstance(operand, Immediate):
            raise ValueError(f"expected an immediate, got {operand!r}")
        return str(operand.value)
