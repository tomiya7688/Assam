"""Core v1 のtext診断(安定した診断コード・位置・原文行)を表す。"""

from __future__ import annotations

from dataclasses import dataclass


# {"責務": "Core v1 parserが返す1件の診断を保持する", "フィールド": ["code: 互換契約となる安定した診断コード", "message: 人向けの説明(文言は変わりうる)", "line: 1始まりの行番号", "column: 1始まりの桁(行頭は1)", "source_line: 診断対象の原文1行"], "副作用": [], "エラー": []}
@dataclass(frozen=True)
class CoreDiagnostic:
    code: str
    message: str
    line: int
    column: int
    source_line: str

    # {"責務": "診断をJSON互換のdictに変換する", "処理": ["5項目をそのまま辞書化"], "引数": [], "戻り値": ["code/message/line/column/source_lineのdict"], "副作用": [], "エラー": []}
    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "source_line": self.source_line,
        }

    # {"責務": "診断を1行の表示文字列にする", "処理": ["行:桁 コード メッセージの形に整形"], "引数": [], "戻り値": ["表示用の1行文字列"], "副作用": [], "エラー": []}
    def __str__(self) -> str:
        return f"{self.line}:{self.column}: {self.code}: {self.message}"


# {"責務": "Core v1 parseの失敗を診断の一覧つきで知らせる", "フィールド": ["diagnostics: 診断のタプル(1件以上、最大件数まで)"], "副作用": [], "エラー": [], "補足": "CLIが既存のValueError経路で非0終了できるようValueErrorを継承する"}
class CoreParseError(ValueError):
    # {"責務": "診断一覧から例外を作る", "処理": ["診断をタプルで保持", "診断を改行で連結した文面を親に渡す"], "引数": ["diagnostics: 診断のシーケンス"], "戻り値": [], "副作用": [], "エラー": []}
    def __init__(self, diagnostics) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__("\n".join(str(item) for item in self.diagnostics))
