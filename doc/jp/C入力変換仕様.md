# C入力変換の初期仕様

言語: 日本語 | [English](../en/c-input-translation.md)

`assam.c_frontend.CTranslator` は、依存ライブラリを追加せずに試せる小さなCサブセットをASSAMへ変換する。

## 対応範囲

- `int main()` または `int main(void)` を一つ
- `int` のローカル変数宣言（初期化あり・なし）
- 宣言済み変数への代入
- 整数リテラル（10進・16進）、変数、括弧
- 単項 `+` / `-`、二項 `+` / `-` / `*` / `/` / `%`
- 最後の文としての `return 整数式;`
- `//` と `/* ... */` コメント

宣言のみの変数はASSAMで0に初期化する。戻り値は `r0` に置き、変換結果に `Halt` を付ける。Cの整数除算規則に合わせてASSAMのDivideは0方向へ丸め、Moduloは被除数と同じ符号の剰余とする。

## 対応しない構文

条件分岐、ループ、関数呼び出し、引数、グローバル変数、配列、ポインタ、浮動小数点、複合代入、インクリメント、複数の宣言子は対象外。非対応構文や未宣言変数は `ValueError` として報告する。

## 使用方法

```text
python -m assam.cli from-c examples/sum.c -o examples/sum.assam
python -m assam.cli run examples/sum.assam
```
