# レジストリとconformance

言語: 日本語 | [English](../../en/design/registry-and-conformance.md)

対象Issue: #2（機械可読schema）、#13（CIゲート）、#8（条件分岐）。決定: DEC-10, PRO-07, PRO-11。

## 1. 役割

registryは**命令契約と対応情報**の正本であり、実行ロジックは含まない。実装（Python/Go/Java/Rust）は、registryを読み込むかコード生成で使い、opcode・operand arity・効果を独自に持たない。意味論そのものは[Core意味論](Core意味論.md)が正本で、registryはその機械可読な要約とリンクを持つ。

## 2. registry schema v3

現行のv2は、Core Draftの効果（read/write位置、memory効果、整数parameter位置、trap条件、`target_mapping_id`、flow）を持つが、幅/符号が`not_decided`でFull名とCore名が混在している。v3は次を満たす。

```jsonc
{
  "schema_version": 3,
  "profiles": {
    "full": {},
    "core": { "versions": ["1"] },
  },
  "instructions": [
    {
      "id": "core.add", // 版を越えて安定する識別子
      "mnemonic": "add", // canonical（Coreは小文字）
      "aliases": [], // Core/canonicalでは空。Full側は full.names
      "availability": [
        { "profile": "core", "since": "1" },
        { "profile": "full" },
      ],
      "full_names": ["Add", "add"], // Fullのcase-insensitive表記
      "operands": [
        { "role": "dest", "kind": "register", "access": "write" },
        { "role": "src", "kind": "register", "access": "read" },
        { "role": "src", "kind": "register", "access": "read" },
      ],
      "width": { "bits": 64, "signedness": "agnostic" }, // "signed" | "unsigned" | "agnostic"
      "effects": {
        "registers": "by_operand",
        "memory": { "read": false, "write": false, "width_bits": null },
        "control": "next", // next | jump | conditional | link | indirect | halt | trap
      },
      "traps": [], // 例: ["div_by_zero"]
      "semantics": "doc/jp/設計/Core意味論.md#22-算術ビット",
      "target_mapping_id": "assam.core.1.add",
      "classification": "ordinary", // ordinary | abi_primitive
    },
  ],
}
```

要点:

- `id`は版を越えて不変。意味が変わる変更は**新しいcore版**として別エントリ（または`availability`の分割）で表す。
- `kind`は`register` / `immediate` / `symbol`(label) / `memory_offset` / `helper_id` / `trap_code`のいずれか。範囲（`min`,`max`）をoperand側に持てる。
- `mnemonic`が正式表記。Fullのaliasは`full_names`に限定し、Coreのparserはこれを見ない（[文法](Core文法とprofile契約.md)）。
- `target_mapping_id`に版を含める（`assam.core.1.<name>`）。Draftの`assam.core.draft.*`は廃止し、対応表は版ごとに作る。
- `classification: abi_primitive`は3ターゲット網羅の例外分類（`hcall`など）。分類を持たない通常opcodeはCIが3ターゲット網羅を要求する。
- 実行ハンドラ識別子はPython実装固有のため registry から外し、Python側で`id`→実装を引く表に移す。registryは実行方法を決めない。

### 2.1 移行

| 項目   | 方針                                                                                                                    |
| ------ | ----------------------------------------------------------------------------------------------------------------------- |
| v2→v3  | 変換スクリプトは作らず、v3を手書きして`tests`で「Full命令がv2と同じ受理/拒否になること」を回帰検証する                  |
| 共存   | 一定期間は`instruction_registry.json`(v3)のみを同梱。v2を読むのは過去の対応表検査に使うtestだけに限定し、v3完了時に削除 |
| schema | `instruction-registry-v3.schema.json`を追加し、registry自身をschema検証する                                             |

### 2.2 検証（実行前に弾く）

- schema検証（開発依存の`jsonschema`をdev extraに追加。ランタイムは標準ライブラリのみ）。
- 一貫性検査: `id`・`mnemonic`の重複なし、`full_names`の衝突なし、`traps`はCore意味論のtrap kind列挙内、`target_mapping_id`の重複なし、`ordinary`は3ターゲットすべてに`in_scope`宣言がある。
- 「registryにある」=「実行時switchに到達する前に検証される」。未知/不正命令はVM生成時に拒否（#2）。

### 2.3 Goなど他言語での利用

- registryは単独のJSONとして配布し、git tag（`registry-v3.N`）とsha256で固定する。Go側は`go:embed`または生成物として取り込み、sha256をテストで固定する。
- 変更時は、registryのsha256が変わったら全conformance corpusを再実行するCIが必須（drift検出）。
- 将来のコード生成は`assam registry export --format <go|json>`のように追加できるが、出力は決定的に同一でなければならない。

## 3. conformance corpus

### 3.1 場所と形式

`examples/conformance/`に、1ケース=1 JSONで置く。複数VM・変換結果が**同じファイル**を読む。

```jsonc
{
  "schema_version": 1,
  "id": "core1.branch.beq.false-no-side-effect",
  "category": "execution", // parse | execution | translation
  "profile": { "name": "core", "version": "1" },
  "description": "...",
  "source": { "text": "const r1, 1\n..." }, // または {"ir": {...}}
  "environment": {
    "memory_bytes": 4096,
    "memory_segments": [],
    "max_steps": 10000,
  },
  "expect": {
    /* categoryごと */
  },
}
```

- `parse`: 期待は`{"accepted": true, "canonical": "..."}` または`{"accepted": false, "diagnostics": [{"code","line"}]}`。
- `execution`: 期待は[Core意味論 §3](Core意味論.md)の観測JSON（`status`, `trap`, `registers`, `memory_sha256`）。
- `translation`: ターゲット/profile別の期待命令列（golden）。実行等価は別（[ターゲット変換](ターゲット変換.md)）。
- 現行の`examples/conformance/conditional-branches.json`（Draft/Full向け）は、新形式に移行し、`profile`でFullを明示して残す。

### 3.2 必須カテゴリ

1. 全命令の通常値・境界値・`r0`
2. 全trapと「trap時に副作用なし」
3. 条件分岐の両経路・正式名/別名（Fullのみ）・即値/レジスタ・前方/後方label・非選択経路の副作用なし（#8）
4. メモリ幅・符号拡張・非整列・範囲外・折返し
5. `jal`/`jr`による呼出し・復帰の入れ子
6. 解析（canonical往復、診断コード）
7. Full互換（#10のstring operand往復、alias）
8. x\*/checked overflowの代表lowering列（backend側が作るが、Coreとして正しい挙動を検証）

### 3.3 実行系のプロトコル

各実装は`<impl> conformance-case <case.json>`で観測JSONを標準出力に出す。`assam conformance run --impl <cmd>`が全ケースを走らせ、期待と比較し、差分を報告する。Python参照実装は`assam conformance run`の既定。差分は**参照実装を正**とするが、参照実装がDEC/設計と矛盾するなら設計を優先して参照実装を直す。

## 4. CIゲート（#13）

PRとmainへのpushで次を必須にする。現状（pytest、変更PythonファイルのRuff整形、pip/証明書検査、対応表検査）に追加する。

| ゲート              | 内容                                                                                 | 状態                                       |
| ------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------ |
| テスト              | `pytest`（Python 3.10/3.12）                                                         | 済                                         |
| 整形                | 変更Pythonファイルの`ruff format --check`                                            | 済                                         |
| 文書整形            | Markdown/YAMLの`prettier --check`（変更ファイル）                                    | 運用中のworkflowに記載。未導入ならA2で導入 |
| 構文/importチェック | `python -m compileall -q assam tests` と全モジュールimport                           | A2                                         |
| パッケージsmoke     | wheel/sdistをbuildして別venvへインストールし`assam --help`と同梱データの存在を確認   | A2                                         |
| CLI smoke           | `parse`/`json`/`run`/`analyze`/`from-c`の最小ケース                                  | A2                                         |
| malformed corpus    | 不正入力が`ValueError`/診断で拒否され、生の`TypeError`/`KeyError`が漏れない          | A2（#11・#12の再発防止）                   |
| 決定的再生          | 同じ入力を2回実行して観測結果が一致                                                  | A2                                         |
| schema検証          | registry・IR・対応表・manifestのschema                                               | B3                                         |
| conformance         | corpus全件（参照実装）。registry変更時は必須                                         | B5                                         |
| 対応表網羅          | 3ターゲットの網羅宣言・対応表照合（現行）。v1命令で再構成                            | C3                                         |
| 型検査              | 現時点では採用しない（標準ライブラリのみ・小規模のため）。採用する場合は設計PRで固定 | 未採用                                     |

失敗した変更をgreen扱いしない: ブランチ保護で必須チェックにする設定は人間（リポジトリ管理者）の作業。設定されるまでは、ワークフロー上「CI成功がマージ条件」を運用で守る。

## 5. 受け入れ条件

- WP-B3: registry v3とschema、v1の全命令定義、一貫性検査、v2との回帰検証が通る。
- WP-B5: corpus形式、runner、必須カテゴリ（上記1〜7）の初期セット、CI必須化。
- WP-A2: 上記A2の全ゲートがCIに入り、意図的に壊した入力で失敗することを確認した記録がPRにある。
