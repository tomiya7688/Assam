# ASSAM

言語: 日本語 | [English](README.en.md)

ASSAM (Assembly Abstract Machine) のPythonリファレンス実装です。

現在は、テキスト構文、JSON IR、基本VM、デバッガー、仮想端末バスを実装しています。

```python
from assam import VM, parse_program
program = parse_program("Move r0 2\nAdd r1 r0 3\nHalt")
print(VM(program).run()["r1"])
```

CLI:

```text
python -m assam.cli run program.assam
python -m assam.cli run core-program.assam --profile core
python -m assam.cli json program.assam -o program.json
python -m assam.cli json core-program.assam --profile core -o core-program.json
python -m assam.cli run program.json --json
python -m assam.cli from-c examples/sum.c -o examples/sum.assam
python -m assam.cli analyze examples/sum.assam
python -m assam.cli analyze examples/sum.assam --format json
python -m assam.cli analyze core-program.assam --profile core
```

`core` は Core 命令だけを許可する検証プロファイルです。Parser、VM、C入力変換器、静的解析器が共通の[命令レジストリ](assam/data/instruction_registry.json)を参照します。命令レジストリはschema v2で、各命令のレジスタread/write位置、ゲストデータメモリ効果、命令固有trap条件を記録します。Core命令にはターゲット対応表用hook IDも付けています。x86-64・ARM64・RV64IのDraft対応表はありますが、いずれも実行可能な変換や意味の同等性を証明しません。`check-target-matrix` は複数の `--mapping` とカバレッジ宣言の対応を構造的に検査できます。整数幅・符号と呼出規約も未決定です。[JSON IR全体のSchema](assam/data/program-ir-v1.schema.json)とCore印の[Schema](assam/data/assam-core-profile-draft.schema.json)も同梱しています。印のない従来JSONは従来どおりFullとして扱います。現在の範囲と設計条件は [Assam Core Profile](doc/jp/assam-core.md) を参照してください。

JSON IR読込時にはラベル名と命令添字の型・範囲を検査し、不正な表を実行前に `ValueError` で拒否します。詳細は [命令セット仕様](doc/jp/命令セット仕様.md) を参照してください。

`from-c` はC全体をコンパイルする機能ではありません。`int main` 内の整数変数、初期化、代入、`+ - * / %`、括弧、単項符号、最後の `return` をASSAMへ変換します。分岐、ループ、関数呼び出し、ポインタ、型変換は対象外です。戻り値はVMの `r0` に格納します。

対応範囲と制約は [C入力変換仕様](doc/jp/C入力変換仕様.md) を参照してください。`examples/sum.c` と `examples/sum.assam` は変換例です。

仕様・開発資料は [日本語ドキュメント](doc/jp/README.md) または [English documentation](doc/en/README.md) から参照できます。
