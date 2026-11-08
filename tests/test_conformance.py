"""conformance runner(WP-B5)の検査: 全ケース実行・差分検出・外部実装プロトコル・CLI。"""

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from assam.cli import main
from assam.conformance_case import ConformanceCase
from assam.conformance_runner import ConformanceRunner

CASES = Path(__file__).resolve().parents[1] / "examples/conformance/cases"


class ConformanceRunnerTest(unittest.TestCase):
    def test_all_shipped_cases_pass_with_python_reference(self):
        report = ConformanceRunner().run_directory(CASES)
        failures = [r for r in report["results"] if r["status"] != "passed"]
        # Core実行ケースはWP-B4待ちのため、現時点では含まれない
        self.assertEqual(failures, [])
        self.assertGreaterEqual(report["total"], 20)

    def test_mismatch_is_reported_as_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = json.loads((CASES / "parse-golden-canonical.json").read_text(encoding="utf-8"))
            data["expect"]["canonical"] = "    halt\n"
            path = Path(tmp, "bad.json")
            path.write_text(json.dumps(data), encoding="utf-8")
            result = ConformanceRunner().run_case(ConformanceCase.load(path))
            self.assertEqual(result["status"], "failed")

    def test_invalid_case_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "x.json")
            path.write_text(json.dumps({"schema_version": 9}), encoding="utf-8")
            with self.assertRaises(ValueError):
                ConformanceCase.load(path)

    def test_external_implementation_protocol(self):
        # 外部実装: 'conformance-case <path>' に対しPython参照の観測を返すスクリプト
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp, "impl.py")
            script.write_text(
                "import json, sys\n"
                "sys.path.insert(0, %r)\n"
                "from assam.conformance_case import ConformanceCase\n"
                "from assam.conformance_runner import observe_python\n"
                "print(json.dumps(observe_python(ConformanceCase.load(__import__('pathlib').Path(sys.argv[2])))))\n"
                % str(Path(__file__).resolve().parents[1])
                .replace("\\", "/"),
                encoding="utf-8",
            )
            runner = ConformanceRunner(impl=f"{sys.executable} {script}")
            report = runner.run_directory(CASES)
            self.assertEqual(report["failed"], 0, report)

    def test_external_failure_is_reported_not_raised(self):
        result = ConformanceRunner(impl=f"{sys.executable} -c 'import sys; sys.exit(3)'").run_case(
            ConformanceCase.load(CASES / "parse-golden-canonical.json")
        )
        self.assertEqual(result["status"], "error")

    def test_cli_exit_codes(self):
        self.assertEqual(main(["conformance", "run", "--cases", str(CASES)]), 0)
        with tempfile.TemporaryDirectory() as tmp:
            data = json.loads((CASES / "parse-golden-canonical.json").read_text(encoding="utf-8"))
            data["expect"]["canonical"] = "x\n"
            Path(tmp, "bad.json").write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(main(["conformance", "run", "--cases", tmp]), 1)


if __name__ == "__main__":
    unittest.main()
