# ASSAM

ASSAM (Assembly Abstract Machine) は、複数の実行系・変換先で共有するアセンブリ構文と抽象マシンのプロジェクトです。

実装は **Goを主軸**とし、Pythonを参照・検証に利用します。Java版は予定（#14）、Rust版は将来候補（#15）です。選定の軸はクロスプラットフォーム性と安全性です。言語の採用だけで完全な安全性が得られるわけではなく、VMの入力検証・実行予算・共有テストも必要です。

## Go Core bootstrap（実験的）

`core/` は共有JSON命令定義に基づくGoパーサーと、整数演算・分岐の最初の実行系です。Bitlang VMなどのGo consumerは、このパッケージを利用して文法・命令定義の独自コピーを避けられます。Bitlang-VMリポジトリへの組み込みは別の作業です。

**これはCore v1全体の完成版ではありません。** profileは明示的に `assam-core/v1-draft.1` を指定します。メモリ、call/return用primitive、runtime helper、共通JSON program IR、x64/ARM64/RISC-V変換は未実装で、安定版profileは受理しません。

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
