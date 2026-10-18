# ASSAM

ASSAM (Assembly Abstract Machine) は、複数の実行系・変換先で共有するアセンブリ構文と抽象マシンのプロジェクトです。

実装は **Goを主軸**とし、Pythonを参照・検証に利用します。Java版は予定（#14）、Rust版は将来候補（#15）です。選定の軸はクロスプラットフォーム性と安全性です。言語の採用だけで完全な安全性が得られるわけではなく、VMの入力検証・実行予算・共有テストも必要です。

## Go Core bootstrap（実験的）

`core/` は共有JSON命令定義に基づくGoパーサーと、整数演算・分岐とメモリの実行系です。Bitlang VMなどのGo consumerは、このパッケージを利用して文法・命令定義の独自コピーを避けられます。Bitlang-VMリポジトリへの組み込みは別の作業です。

**これはCore v1全体の完成版ではありません。** 整数演算・分岐は `assam-core/v1-draft.1`、メモリ命令を含む実行は `assam-core/v1-draft.2` を明示指定します。draft.1の受理命令・実行結果は維持します。call/return用primitive、runtime helper、共通JSON program IR、x64/ARM64/RISC-V変換は未実装で、安定版profileは受理しません。

```sh
go run ./cmd/assam-core -profile assam-core/v1-draft.1 examples/core/sum.assam
go test ./...
python -m pip install pytest==9.0.2
python -m pytest -q
```

サンプルはr3に55（JSONでは `0x0000000000000037`）を残して停止します。Goコードは標準ライブラリのみを使用し、Go 1.23以降でビルドできます。開発・配布にはサポート中のGo toolchainを使用してください。

- 共有契約: [`core/registry.json`](core/registry.json)
- 実験的profileの仕様と制約: [`doc/core-bootstrap.md`](doc/core-bootstrap.md)
- 言語非依存のテスト入力・期待値: [`testdata/core-v1.json`](testdata/core-v1.json)
- Python差分検証用oracle: [`tools/core_reference.py`](tools/core_reference.py)

Python oracleは開発用であり、既存の `assam.VM` と同じAPIではありません。

## 境界検査付きメモリ（draft.2）

7種のloadと4種のstoreを追加し、draft.2は計33命令です。64-bitのguestアドレス、little-endian、非整列アクセス、符号付きloadの符号拡張を扱います。範囲外は `memory_out_of_bounds` trapとなり、失敗したstoreは一部分も書き込みません。初期メモリと実行後のメモリは呼び出し元や別実行と共有しません。

```sh
go run ./cmd/assam-core -profile assam-core/v1-draft.2 -memory-bytes 9 -dump-memory examples/core/memory.assam
```

サンプルは6命令で停止し、r3=`0xffffffff89abcdef`、r4=`0x0000000089abcdef`になります。`-dump-memory`を付けた場合だけ最終メモリをhex文字列でJSON出力します。メモリは明示確保した範囲だけが有効で、CLIの既定サイズは0、bootstrapの上限は16 MiBです。これはguestアドレスの64-bit幅とは別のホスト資源上限です。

Go APIは `RunWithMemory(program, budget, initialBytes)`、解決済み命令定義は `SchemaForProfile(profile)` で取得します。メモリ定義は既存22命令を複製せず、[`core/registry-memory.json`](core/registry-memory.json)から継承します。詳細は[メモリ契約](doc/core-memory.md)、共有期待値は[`testdata/core-memory.json`](testdata/core-memory.json)を参照してください。

## 既存Python Fullリファレンス実装

従来のテキスト構文、JSON IR、基本VM、デバッガー、仮想端末バスは維持しています。FullとCoreではレジスタ・演算・文法の契約が異なり、暗黙に混在させません。Full側の既知の監査Issue #7–#12は今回のGo bootstrap追加では修正していません。

```python
from assam import VM, parse_program
program = parse_program("Move r0 2\nAdd r1 r0 3\nHalt")
print(VM(program).run()["r1"])
```

CLI:

```text
python -m assam.cli run program.assam
python -m assam.cli json program.assam -o program.json
python -m assam.cli run program.json --json
```
