"""Core v1 canonical textの厳格なparser(Full parserとは別クラス・別ファイル)。"""

from __future__ import annotations

import re

from .core_diagnostic import CoreDiagnostic, CoreParseError
from .instruction_set import InstructionSet
from .ir import Immediate, Instruction, Program, Register, Symbol

DEFAULT_MAX_DIAGNOSTICS = 20
_REGISTER_COUNT = 32  # r0..r31
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_OPCODE = re.compile(r"[a-z][a-z0-9_]*")
_REGISTER = re.compile(r"r(0|[1-9][0-9]*)")
_DECIMAL = re.compile(r"-?[0-9]+")
_HEX = re.compile(r"-?0x[0-9a-fA-F]+")
# 即値の許容範囲(設計: Core意味論 2.)。constは64bit全値を表せる範囲
_RANGES = {
    "immediate": (-(2**63), 2**64 - 1),
    "memory_offset": (-(2**31), 2**31 - 1),
    "trap_code": (0, 2**32 - 1),
    "helper_id": (0, 2**32 - 1),
}
_MAX_HEX_DIGITS = 16
_BLANKS = " \t"


# {"責務": "Core v1のcanonical textを検査してProgram(型付きoperand)へ変換する", "処理": ["エンコード・行形式・opcode・operand・labelを行単位で検査", "診断を最大件数まで集めて最初の1件で打ち切らない", "診断がなければProgramを返す"], "フィールド": ["_definitions: Core v1命令定義(mnemonicから項目)", "_max: 返す診断の最大件数"], "副作用": [], "エラー": ["診断が1件以上あればCoreParseError"], "補足": "Full parserの分岐や再利用はしない。命令ごとのoperand種別はレジストリに従う"}
class CoreParser:
    # {"責務": "parserを初期化する", "処理": ["Core v1定義表を取得", "診断の最大件数を保存"], "引数": ["max_diagnostics: 診断の最大件数(既定20)"], "戻り値": [], "副作用": [], "エラー": ["最大件数が正の整数でなければValueError"]}
    def __init__(self, max_diagnostics: int = DEFAULT_MAX_DIAGNOSTICS) -> None:
        if type(max_diagnostics) is not int or max_diagnostics < 1:
            raise ValueError("max_diagnostics must be a positive integer")
        self._definitions = InstructionSet().core_v1_definitions()
        self._max = max_diagnostics

    # {"責務": "text全体をProgramへ変換する", "処理": ["BOMを検査", "行ごとにlabel定義か命令かを判定して集める", "未定義label・末尾に命令のないlabelを検査", "診断があれば例外、なければProgramを返す"], "引数": ["text: Core v1のcanonical text"], "戻り値": ["Core v1の印つきProgram"], "副作用": [], "エラー": ["診断が1件以上あればCoreParseError"]}
    def parse(self, text: str) -> Program:
        diagnostics: list[CoreDiagnostic] = []
        instructions: list[Instruction] = []
        labels: dict[str, int] = {}
        label_lines: dict[str, int] = {}
        references: list[tuple[str, int, int, str]] = []
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()  # 末尾の改行で生じる空要素
        if text.startswith("﻿"):
            # BOMは1件だけ報告し、以降の行検査からは外す
            diagnostics.append(
                CoreDiagnostic("core.syntax.encoding", "BOM is not allowed", 1, 1, lines[0])
            )
            lines[0] = lines[0][1:]
        for number, raw in enumerate(lines, 1):
            line = raw[:-1] if raw.endswith("\r") else raw
            found = self._check_encoding(line, number)
            if found:
                diagnostics.extend(found)
                continue
            self._parse_line(
                line, number, instructions, labels, label_lines, references, diagnostics
            )
        for name, number, column, source in references:
            if name not in labels:
                diagnostics.append(
                    CoreDiagnostic(
                        "core.syntax.label_undefined",
                        f"undefined label {name!r}",
                        number,
                        column,
                        source,
                    )
                )
        for name, index in labels.items():
            if index >= len(instructions):
                number = label_lines[name]
                source = lines[number - 1]
                diagnostics.append(
                    CoreDiagnostic(
                        "core.syntax.label_dangling",
                        f"label {name!r} has no instruction after it",
                        number,
                        1,
                        source,
                    )
                )
        if diagnostics:
            diagnostics.sort(key=lambda item: (item.line, item.column))
            raise CoreParseError(diagnostics[: self._max])
        return Program(
            instructions, labels, InstructionSet.core_v1_profile_marker()
        )

    # {"責務": "1行の文字コード・制御文字・コメント外の非ASCIIを検査する", "処理": ["コメント開始位置を求める", "制御文字を全体で検査", "コード部の非ASCIIを検査"], "引数": ["line: 行末の改行を除いた1行", "number: 行番号"], "戻り値": ["診断のリスト(問題なしなら空)"], "副作用": [], "エラー": []}
    @staticmethod
    def _check_encoding(line: str, number: int) -> list[CoreDiagnostic]:
        comment = line.find(";")
        code_end = len(line) if comment < 0 else comment
        for index, ch in enumerate(line):
            if (ord(ch) < 0x20 and ch != "\t") or ord(ch) == 0x7F:
                return [
                    CoreDiagnostic(
                        "core.syntax.encoding",
                        f"control character U+{ord(ch):04X} is not allowed",
                        number,
                        index + 1,
                        line,
                    )
                ]
            if ord(ch) > 0x7F and index < code_end:
                return [
                    CoreDiagnostic(
                        "core.syntax.encoding",
                        "non-ASCII characters are allowed only in comments",
                        number,
                        index + 1,
                        line,
                    )
                ]
        return []

    # {"責務": "コメントを除いた1行をlabel定義または命令として処理する", "処理": ["空行を読み飛ばす", "label定義の単独行を登録", "ほかは命令として検査してProgramへ追加"], "引数": ["line: 1行", "number: 行番号", "instructions: 命令列(更新される)", "labels: label表(更新される)", "label_lines: labelの定義行(更新される)", "references: label参照の記録(更新される)", "diagnostics: 診断(更新される)"], "戻り値": [], "副作用": ["引数の各コンテナを更新する"], "エラー": []}
    def _parse_line(
        self, line, number, instructions, labels, label_lines, references, diagnostics
    ) -> None:
        comment = line.find(";")
        code = line if comment < 0 else line[:comment]
        body = code.strip(_BLANKS)
        if not body:
            return
        start = len(code) - len(code.lstrip(_BLANKS))

        def report(code_id, message, offset):
            diagnostics.append(
                CoreDiagnostic(code_id, message, number, offset + 1, line)
            )

        if ":" in body:
            name = body[:-1] if body.endswith(":") else None
            if name is None or body.count(":") != 1:
                report(
                    "core.syntax.line_form",
                    "a label definition must be alone on its line as 'name:'",
                    start,
                )
                return
            if _IDENT.fullmatch(name) is None:
                report("core.syntax.line_form", f"invalid label name {name!r}", start)
            elif name in self._definitions or self._is_register_name(name):
                report(
                    "core.syntax.label_reserved",
                    f"label name {name!r} is reserved",
                    start,
                )
            elif name in labels:
                report(
                    "core.syntax.label_duplicate",
                    f"duplicate label {name!r}",
                    start,
                )
            else:
                labels[name] = len(instructions)
                label_lines[name] = number
            return
        self._parse_instruction(
            body, start, line, number, instructions, references, diagnostics
        )

    # {"責務": "命令1行のopcodeとoperandを検査してInstructionを追加する", "処理": ["opcodeを小文字・registry照合", "カンマ区切りを分割(空要素は区切り違反)", "operand数と種別・範囲を検査", "問題がなければInstructionを追加"], "引数": ["body: 前後の空白を除いたコード部", "start: 行内でのbodyの開始位置(0始まり)", "line: 原文1行", "number: 行番号", "instructions: 命令列(更新される)", "references: label参照の記録(更新される)", "diagnostics: 診断(更新される)"], "戻り値": [], "副作用": ["命令列・参照・診断を更新する"], "エラー": []}
    def _parse_instruction(
        self, body, start, line, number, instructions, references, diagnostics
    ) -> None:
        def report(code_id, message, offset):
            diagnostics.append(
                CoreDiagnostic(code_id, message, number, offset + 1, line)
            )

        match = re.match(r"[^\s,]+", body)
        opcode = match.group(0)
        definition = (
            self._definitions.get(opcode) if _OPCODE.fullmatch(opcode) else None
        )
        if definition is None:
            report(
                "core.syntax.unknown_opcode",
                f"unknown opcode {opcode!r} (Core opcodes are lowercase canonical names)",
                start,
            )
            return
        rest = body[match.end() :]
        pieces: list[tuple[str, int]] = []
        if rest.strip(_BLANKS):
            offset = start + match.end()
            for part in rest.split(","):
                stripped = part.strip(_BLANKS)
                lead = len(part) - len(part.lstrip(_BLANKS))
                pieces.append((stripped, offset + lead))
                offset += len(part) + 1
        failed = False
        for text, offset in pieces:
            if not text:
                report("core.syntax.separator", "empty operand around a comma", offset)
                failed = True
            elif any(ch in _BLANKS for ch in text):
                report(
                    "core.syntax.separator",
                    "operands must be separated by commas",
                    offset,
                )
                failed = True
        if failed:
            return
        kinds = [operand["kind"] for operand in definition["operands"]]
        if len(pieces) != len(kinds):
            report(
                "core.syntax.operand_count",
                f"{opcode} expects {len(kinds)} operands, got {len(pieces)}",
                start,
            )
            return
        operands = []
        for (text, offset), kind in zip(pieces, kinds):
            operand = self._parse_operand(
                text, kind, offset, number, line, references, report
            )
            if operand is None:
                failed = True
            else:
                operands.append(operand)
        if not failed:
            instructions.append(Instruction(opcode, tuple(operands), number))

    # {"責務": "1つのoperand文字列を期待された種別の型付きoperandへ変換する", "処理": ["引用符はprofile違反", "registry種別(register/symbol/即値系)ごとに形式と範囲を検査", "symbolは参照として記録"], "引数": ["text: operand文字列", "kind: registryが定める種別", "offset: 行内の位置(0始まり)", "number: 行番号", "line: 原文1行", "references: label参照の記録(更新される)", "report: 診断を追加する関数"], "戻り値": ["型付きoperand、不正ならNone(診断はreportで追加済み)"], "副作用": ["referencesとreportを通じた診断を更新する"], "エラー": []}
    def _parse_operand(self, text, kind, offset, number, line, references, report):
        if text.startswith('"'):
            report(
                "core.profile.disallowed",
                "string literals are not allowed in Core",
                offset,
            )
            return None
        if kind == "register":
            match = _REGISTER.fullmatch(text)
            if match is None:
                report(
                    "core.syntax.operand_kind",
                    f"expected a register, got {text!r}",
                    offset,
                )
                return None
            if int(text[1:]) >= _REGISTER_COUNT:
                report(
                    "core.syntax.register_range",
                    f"register {text!r} is outside r0..r31",
                    offset,
                )
                return None
            return Register(int(text[1:]))
        if kind == "symbol":
            if _IDENT.fullmatch(text) is None or self._is_register_name(text):
                report(
                    "core.syntax.operand_kind",
                    f"expected a label name, got {text!r}",
                    offset,
                )
                return None
            references.append((text, number, offset + 1, line))
            return Symbol(text)
        low, high = _RANGES[kind]
        if _HEX.fullmatch(text):
            digits = text.lstrip("-")[2:]
            if len(digits) > _MAX_HEX_DIGITS:
                report(
                    "core.syntax.immediate_range",
                    f"hex immediate {text!r} has more than 16 digits",
                    offset,
                )
                return None
            value = int(text, 16)
        elif _DECIMAL.fullmatch(text):
            value = int(text)
        else:
            report(
                "core.syntax.operand_kind",
                f"expected an immediate, got {text!r}",
                offset,
            )
            return None
        if not low <= value <= high:
            report(
                "core.syntax.immediate_range",
                f"immediate {text!r} is outside [{low}, {high}]",
                offset,
            )
            return None
        return Immediate(value)

    # {"責務": "名前がレジスタ予約語(r0..r31)か判定する", "処理": ["rと数字の形で範囲内か確認"], "引数": ["name: 判定する名前"], "戻り値": ["予約語ならTrue"], "副作用": [], "エラー": []}
    @staticmethod
    def _is_register_name(name: str) -> bool:
        return _REGISTER.fullmatch(name) is not None and int(name[1:]) < _REGISTER_COUNT
