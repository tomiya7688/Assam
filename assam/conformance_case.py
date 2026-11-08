"""conformanceケース(1ファイル=1 JSON)の読込みと構造検査。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CASE_SCHEMA_VERSION = 1
CATEGORIES = ("parse", "execution")
PROFILES = ("core", "full")


# {"責務": "1件のconformanceケースを保持し、構造を検査する", "フィールド": ["path: 読み込んだファイル", "data: 検査済みのケースdict", "id/category/profile: 基本項目"], "副作用": [], "エラー": ["構造不正でValueError"]}
@dataclass(frozen=True)
class ConformanceCase:
    path: Path
    data: dict[str, Any]

    # {"責務": "ケースファイルを読んで検査する", "処理": ["JSON読込み", "必須キーと型を検査", "categoryごとの期待値形式を検査"], "引数": ["path: ケースJSONのパス"], "戻り値": ["ConformanceCase"], "副作用": ["ファイルを読む"], "エラー": ["読込み失敗・構造不正でValueError"]}
    @classmethod
    def load(cls, path: Path) -> "ConformanceCase":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path}: cannot read case: {exc}") from exc
        cls._check(path, data)
        return cls(path, data)

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def category(self) -> str:
        return self.data["category"]

    @property
    def profile(self) -> str:
        return self.data["profile"]["name"]

    # {"責務": "ケースdictの構造を検査する", "処理": ["schema_version・id・category・profile・sourceを検査", "expectのcategory別形式を検査"], "引数": ["path: 診断用のパス", "data: ケースdict"], "戻り値": [], "副作用": [], "エラー": ["不正でValueError"]}
    @staticmethod
    def _check(path: Path, data: Any) -> None:
        def fail(message: str):
            raise ValueError(f"{path}: {message}")

        if not isinstance(data, dict):
            fail("case must be an object")
        if data.get("schema_version") != CASE_SCHEMA_VERSION:
            fail("unsupported schema_version")
        if not isinstance(data.get("id"), str) or not data["id"]:
            fail("id must be a non-empty string")
        if data.get("category") not in CATEGORIES:
            fail(f"category must be one of {CATEGORIES}")
        profile = data.get("profile")
        if not isinstance(profile, dict) or profile.get("name") not in PROFILES:
            fail(f"profile.name must be one of {PROFILES}")
        if data["category"] == "parse" and profile["name"] != "core":
            fail("parse cases are Core v1 cases")
        source = data.get("source")
        if not isinstance(source, dict) or not isinstance(source.get("text"), str):
            fail("source.text must be a string")
        expect = data.get("expect")
        if not isinstance(expect, dict):
            fail("expect must be an object")
        if data["category"] == "parse":
            if type(expect.get("accepted")) is not bool:
                fail("parse expect.accepted must be a boolean")
            if expect["accepted"] and not isinstance(expect.get("canonical"), str):
                fail("accepted parse case needs expect.canonical")
            if not expect["accepted"] and not isinstance(expect.get("diagnostics"), list):
                fail("rejected parse case needs expect.diagnostics")
        else:
            if expect.get("status") not in ("halted", "trap"):
                fail("execution expect.status must be halted or trap")
            if "memory" in expect and not isinstance(expect["memory"], dict):
                fail("execution expect.memory must be an object")
