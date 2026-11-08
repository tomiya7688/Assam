"""conformanceケースを実装(内蔵のPython参照、または外部コマンド)で実行し、期待値と比較する。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from .conformance_case import ConformanceCase
from .core_diagnostic import CoreParseError
from .core_parser import CoreParser
from .parser import parse_program
from .vm import VM

DEFAULT_STEPS = 100000


# {"責務": "ケース集合を実装で実行し、期待との差分を集計する", "処理": ["ケースを読込み", "各ケースの観測を実装から得る", "期待と比較して結果を積む"], "フィールド": ["impl: 外部コマンド(空ならPython参照実装)", "timeout: 外部コマンドの制限秒数"], "副作用": ["外部コマンドを起動する(指定時)"], "エラー": ["ケースの構造不正はValueError"]}
class ConformanceRunner:
    # {"責務": "runnerを初期化する", "処理": ["実装コマンドを保存"], "引数": ["impl: 外部実装のコマンド(文字列、省略時はPython参照)", "timeout: 外部実行の制限秒数"], "戻り値": [], "副作用": [], "エラー": []}
    def __init__(self, impl: str | None = None, timeout: float = 60.0) -> None:
        self.impl = impl
        self.timeout = timeout

    # {"責務": "ケースディレクトリ全体を実行して報告を返す", "処理": ["*.jsonを名前順に読込み", "各ケースを実行・比較", "件数を集計"], "引数": ["cases_dir: ケースのディレクトリ"], "戻り値": ["報告dict(total/passed/failed/results)"], "副作用": ["ファイル読込み・外部コマンド起動"], "エラー": ["ケース構造不正はValueError"]}
    def run_directory(self, cases_dir: Path) -> dict:
        cases = [ConformanceCase.load(path) for path in sorted(cases_dir.glob("*.json"))]
        results = [self.run_case(case) for case in cases]
        failed = [item for item in results if item["status"] != "passed"]
        return {
            "total": len(results),
            "passed": len(results) - len(failed),
            "failed": len(failed),
            "results": results,
        }

    # {"責務": "1ケースを実行して期待と比較する", "処理": ["観測を取得", "期待と一致すれば成功、違えば差分を記録", "実装の失敗は失敗として記録"], "引数": ["case: ケース"], "戻り値": ["結果dict(id, status, expected, actual)"], "副作用": [], "エラー": []}
    def run_case(self, case: ConformanceCase) -> dict:
        expected = case.data["expect"]
        try:
            actual = self._observe(case)
        except Exception as exc:  # 実装の失敗は差分として報告する
            return {"id": case.id, "status": "error", "expected": expected, "actual": str(exc)}
        comparable = self._restrict(actual, expected)
        status = "passed" if comparable == expected else "failed"
        return {"id": case.id, "status": status, "expected": expected, "actual": comparable}

    # {"責務": "期待に含まれる項目だけを観測から取り出す", "処理": ["期待のキーだけを残す"], "引数": ["actual: 観測dict", "expected: 期待dict"], "戻り値": ["比較用dict"], "副作用": [], "エラー": []}
    @staticmethod
    def _restrict(actual: dict, expected: dict) -> dict:
        return {key: actual.get(key) for key in expected}

    # {"責務": "ケースの観測を実装から得る", "処理": ["外部実装ならコマンドを起動してJSONを読む", "内蔵実装ならPython参照で観測する"], "引数": ["case: ケース"], "戻り値": ["観測dict"], "副作用": ["外部コマンドを起動(指定時)"], "エラー": ["外部実装の失敗・不正なJSONでRuntimeError"]}
    def _observe(self, case: ConformanceCase) -> dict:
        if self.impl is None:
            return observe_python(case)
        command = [*self.impl.split(), "conformance-case", str(case.path)]
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout, check=False
        )
        if completed.returncode != 0:
            raise RuntimeError(f"implementation exited {completed.returncode}")
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"implementation output is not JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeError("implementation output must be an object")
        return value


# {"責務": "内蔵のPython参照実装でケースを観測する", "処理": ["parseはCore v1 parserで受理・診断・canonicalを得る", "executionはFull VMを実行して停止・レジスタ・メモリを得る"], "引数": ["case: ケース"], "戻り値": ["観測dict(accepted/canonical/diagnostics または status/registers/memory/memory_sha256)"], "副作用": [], "エラー": ["Core実行はRuntimeError(B4待ち)"]}
def observe_python(case: ConformanceCase) -> dict:
    if case.category == "parse":
        try:
            program = CoreParser().parse(case.data["source"]["text"])
        except CoreParseError as exc:
            return {
                "accepted": False,
                "diagnostics": [
                    {"code": item.code, "line": item.line} for item in exc.diagnostics
                ],
            }
        from .core_emitter import CoreEmitter

        return {"accepted": True, "canonical": CoreEmitter().emit(program)}
    if case.profile != "full":
        raise RuntimeError("Core execution needs the Core v1 VM (WP-B4)")
    limit = case.data.get("environment", {}).get("max_steps", DEFAULT_STEPS)
    vm = VM(parse_program(case.data["source"]["text"]), profile="full")
    try:
        vm.run(max_steps=limit)
    except Exception:
        return {"status": "trap"}
    memory = {str(address): value for address, value in sorted(vm.memory.items())}
    digest = hashlib.sha256(
        "".join(f"{a}:{v}\n" for a, v in sorted(vm.memory.items())).encode("ascii")
    ).hexdigest()
    return {
        "status": "halted" if vm.halted else "running",
        "registers": dict(vm.registers),
        "memory": memory,
        "memory_sha256": digest,
    }
