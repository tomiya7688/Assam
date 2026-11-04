# Core意味論（Core v1）

言語: 日本語 | [English](../../en/design/core-semantics.md)

対象Issue: #3（Core ISAの実行意味）、#2・#4へ接続。決定: DEC-02〜DEC-09, DEC-14、PRO-01〜PRO-09。

> 区分: 「確定」はIssue #3のconsumer contractに明記された事項、「提案」は本設計が決めた部分。未決はQ1（`mulhu`/`mulhs`）のみ。

## 1. マシンモデル

| 項目     | 定義                                                                                             | 区分              |
| -------- | ------------------------------------------------------------------------------------------------ | ----------------- |
| レジスタ | `r0`〜`r31`、各64bit。初期値0。`r0`は読むと常に0、書き込みは破棄                                 | 確定              |
| PC       | 命令index（0始まり）。通常は`+1`、分岐命令だけが変更する                                         | 提案              |
| 整数     | 値は64bit符号なしビット列。符号付き命令は2の補数として解釈する。加減乗は modulo 2^64             | 確定              |
| メモリ   | 独立したbyte-addressed空間、サイズ`memory_bytes`（インスタンスパラメータ）、ゼロ初期化、連続領域 | 確定+提案(PRO-08) |
| アドレス | 64bit。有効アドレス`ea = (rbase + sext(off)) mod 2^64`                                           | 確定+提案         |
| endian   | little-endian。非整列アクセス可                                                                  | 確定              |
| 隠れ状態 | なし。call stack・フラグ・暗黙のlink registerを持たない                                          | 確定              |
| 終了     | `halt`または未処理のtrap。命令列の末尾を越えて暗黙停止しない                                     | 提案              |

実行1ステップ: 命令を実行→（trapしなければ）PC更新。**trapした命令は副作用を残さない**（レジスタ・メモリ・PCを更新しない。ただし観測結果にtrapしたPCを含める）。

## 2. 命令一覧

表記: `rd`=書き込みレジスタ、`rs`=読み込みレジスタ、`imm`=即値、`L`=label。値の記号は`u`=符号なし64bit、`s`=符号付き64bit。

### 2.1 データ移動

| 命令    | 形              | 意味                                             |
| ------- | --------------- | ------------------------------------------------ |
| `const` | `const rd, imm` | `rd = imm mod 2^64`。許容範囲は`[-2^63, 2^64-1]` |
| `mov`   | `mov rd, rs`    | `rd = rs`                                        |

### 2.2 算術・ビット

| 命令              | 形                   | 意味                                                                                                        |
| ----------------- | -------------------- | ----------------------------------------------------------------------------------------------------------- |
| `add` `sub` `mul` | `op rd, rs1, rs2`    | modulo 2^64                                                                                                 |
| `mulhu`           | `mulhu rd, rs1, rs2` | 符号なし128bit積の上位64bit（**Q1: 含める推奨**）                                                           |
| `mulhs`           | `mulhs rd, rs1, rs2` | 符号付き128bit積の上位64bit（**Q1**）                                                                       |
| `divu` `remu`     | `op rd, rs1, rs2`    | 符号なし商/剰余。`rs2==0`は`div_by_zero` trap                                                               |
| `divs` `rems`     | `op rd, rs1, rs2`    | 符号付き（0方向丸め）。`rs2==0`は`div_by_zero` trap。`MIN / -1 = MIN`、`MIN % -1 = 0`（trapしない。PRO-03） |
| `and` `or` `xor`  | `op rd, rs1, rs2`    | ビット演算                                                                                                  |
| `not`             | `not rd, rs`         | ビット反転                                                                                                  |
| `shl`             | `shl rd, rs1, rs2`   | 論理左。シフト量は`rs2 & 63`                                                                                |
| `shr`             | `shr rd, rs1, rs2`   | 論理右。シフト量は`rs2 & 63`                                                                                |
| `sar`             | `sar rd, rs1, rs2`   | 算術右。シフト量は`rs2 & 63`                                                                                |

### 2.3 比較

| 命令   | 形                  | 意味                        |
| ------ | ------------------- | --------------------------- |
| `seq`  | `seq rd, rs1, rs2`  | `rd = (rs1 == rs2) ? 1 : 0` |
| `slt`  | `slt rd, rs1, rs2`  | 符号付き `rs1 < rs2`        |
| `sltu` | `sltu rd, rs1, rs2` | 符号なし `rs1 < rs2`        |

### 2.4 メモリ

`ea = (rbase + sext(off)) mod 2^64`。`off`は符号付き32bit。アクセス範囲`[ea, ea+w)`が`[0, memory_bytes)`に収まらない（加算の折返し含む）と`memory_out_of_range` trap（アドレスとwidthを報告）。

| 命令                       | 形                    | 意味                                   |
| -------------------------- | --------------------- | -------------------------------------- |
| `ld8u` `ld16u` `ld32u`     | `op rd, rbase, off`   | ゼロ拡張                               |
| `ld8s` `ld16s` `ld32s`     | `op rd, rbase, off`   | 符号拡張                               |
| `ld64`                     | `ld64 rd, rbase, off` | 64bit                                  |
| `st8` `st16` `st32` `st64` | `op rs, rbase, off`   | `rs`の下位wビットをlittle-endianで格納 |

### 2.5 制御

| 命令          | 形               | 意味                                                           |
| ------------- | ---------------- | -------------------------------------------------------------- |
| `jump`        | `jump L`         | `PC = L`                                                       |
| `beq` `bne`   | `op rs1, rs2, L` | 等値/不等値なら`PC = L`、偽なら`PC+1`                          |
| `blt` `bge`   | `op rs1, rs2, L` | 符号付き `<` / `>=`                                            |
| `bltu` `bgeu` | `op rs1, rs2, L` | 符号なし `<` / `>=`                                            |
| `brz` `brnz`  | `op rs, L`       | `rs==0` / `rs!=0` なら`PC = L`                                 |
| `jal`         | `jal rd, L`      | `rd = PC+1`（次命令のindex）; `PC = L`。`rd=r0`なら通常のjump  |
| `jr`          | `jr rs`          | `PC = rs`。`rs`が`[0, 命令数)`外なら`invalid_jump_target` trap |
| `halt`        | `halt`           | 正常停止                                                       |
| `trap`        | `trap imm`       | `explicit` trap。`imm`は`[0, 2^32-1]`                          |
| `hcall`       | `hcall imm`      | runtime helper呼出し（ABI primitive）。§5                      |

関数呼出しは`jal r31, f`、復帰は`jr r31`（r31は慣例であり意味論上特別ではない）。呼出規約（引数・戻り値・callee保存）はBitlang Low backend側のABIであり、Coreは規定しない。

分岐の非選択経路は一切副作用を持たない（#8の条件分岐不具合の再発防止。conformanceで検証）。

### 2.6 静的検証（load時）

実行前に拒否するもの: 未知opcode、operand数/kind違反、レジスタ範囲外、即値範囲外、未定義/重複label、`L`の範囲外、`off`範囲外。`jr`の動的対象のみ実行時trap。

## 3. trap

| kind                  | 条件                                               | 追加情報           |
| --------------------- | -------------------------------------------------- | ------------------ |
| `div_by_zero`         | 除数が0                                            | pc                 |
| `memory_out_of_range` | アクセス範囲がメモリ外                             | pc, address, width |
| `invalid_jump_target` | `jr`の対象が範囲外、または`PC`が命令列末尾を越える | pc, target         |
| `unknown_helper`      | `hcall`のidが未登録                                | pc, id             |
| `explicit`            | `trap imm`                                         | pc, code           |

- ステップ上限・メモリ確保失敗・I/O失敗などの**環境制限はtrapではない**（別の`limit`結果として報告）。
- 観測結果（PRO-07）: `{"status":"halted"|"trapped"|"limit", "trap":{"kind","pc",...}, "registers":[32個のu64（10進文字列）], "memory_sha256":"..."}`。レジスタは10進文字列（JSONの53bit精度問題を避けるため）。実装間比較はこの形で行う。
- trap kindの追加・変更は互換契約。変更はregistryの版を上げる。

## 4. Bitlang Lowからの要件の落とし込み

Coreは次を**命令として追加せず**、loweringで満たす（DEC-09）。

- **checked overflow**: 符号付き加算`c = a + b`のoverflowは、`xor`/`and`/`slt`で`((a ^ c) & (b ^ c)) < 0`を判定し、真なら`trap`へ分岐する。乗算overflowは`mulhs`（Q1）で上位64bitを符号拡張と比較する。
- **任意の意味幅**（8/16/32bit等）: 64bit演算後に`shl`+`sar`/`shr`で符号/ゼロ拡張して幅を保つ。
- **64bit超**（x*を含む）: backendがlimb列（64bit word）へlowerし、carry/borrowは`sltu`で得る。例: 128bit加算`(hi,lo)=(ah,al)+(bh,bl)`は`add lo`・`sltu c, lo, al`・`add hi`・`add hi, hi, c`。`Int<Radix>x*`/`Uint<Radix>x*`は固定幅や切り詰めで代用せず、動的limbまたはruntime helper（`hcall`）で扱う。数値型の`x0`は無効で`x*`の別名ではない。`Float<Radix>x\*`は拒否し、host floatで代用しない（Q5）。
- **zero-payload**: 論理要素数と物理サイズを区別する。stride 0でもアドレス算術を論理indexの代わりにせず、bounds検査は比較+分岐+`trap`で明示する。identity/Ref/borrow/lifetimeが観測可能ならdescriptorをbackendが明示的に保持する。Coreは配列/参照の概念を持たない。
- **bounds/check/trap列**: `sltu`+`brz`/`brnz`+`trap`の組合せ。
- **shift量検証**: 下位6bitを使う契約（DEC-04）。範囲外シフトをtrapさせたい意味はbackendが`sltu`+`trap`で明示する。

BitlangのOwnership/borrow/Ref/cleanup/class/closureの意味検証・低下はCoreの前に済ませ、Coreは再解析しない。

## 5. `hcall`（helper-call、ABI primitive）

- `hcall imm`: runtime helper番号`imm`を呼ぶ。引数は`r1`〜`r6`、結果は`r1`〜`r2`、他のレジスタは保存（helperが壊してよい範囲はhelper ABI表で定義）。
- helper番号の意味はBitlang Low [runtime-helper ABI](https://github.com/tomiya7688/Bitlang_low/blob/main/docs/runtime-helper-abi.md)に従い、Assamは番号空間と呼出規約・trap扱いだけを定義する。**v1ではAssam自身が定義する標準helperを持たない**（登録された番号だけが有効）。conformanceでは登録・未登録の両方を検証する。
- 変換: x64/ARM64/RISC-Vでは対応表の`abi_helper`参照（`assam_helper_<id>`シンボル呼出し）に展開する。これはDEC-12の「runtime/ABI primitiveの明示例外」であり、通常opcodeの3ターゲット網羅とは別分類にする。

## 6. Draft（現行Core）からの対応

| Draft                    | v1                                                      | 備考                                 |
| ------------------------ | ------------------------------------------------------- | ------------------------------------ |
| `Move r, imm`            | `const rd, imm`                                         | 即値代入                             |
| `Move r, r`              | `mov rd, rs`                                            |                                      |
| `Add/Subtract/Multiply`  | `add/sub/mul`                                           | operandはレジスタのみ（PRO-02）      |
| `Divide/Modulo`          | `divs/rems`（Pythonの0方向丸めと一致）または`divu/remu` | 符号の選択が必要                     |
| `And/Or/Xor/Not`         | `and/or/xor/not`                                        |                                      |
| `ShiftLeft/ShiftRight`   | `shl` / `shr`または`sar`                                | 負のシフトtrapはv1で消え、下位6bit化 |
| `Compare r, a, b`        | `seq rd, rs1, rs2`                                      |                                      |
| `Load/Store`             | `ld64`/`st64`（幅を選ぶ）                               | 疎memory→連続memory                  |
| `Jump`                   | `jump`                                                  |                                      |
| `JumpEqual/JumpNotEqual` | `beq/bne`                                               |                                      |
| `Call` / `Return`        | `jal r31, L` / `jr r31`                                 | 隠れたcall stackの廃止               |
| `Halt`                   | `halt`                                                  |                                      |

C frontendはv1 canonicalを出力するよう移行する（WP-B6）。

## 7. 受け入れ条件（WP-B4）

- Python参照VM（`core` v1）が上記の全命令・trapを実装し、corpusで検証されている。
- 各命令に最低: 通常値・境界値（0、1、`-1`、`MIN`、`MAX`）・`r0`への書込み・trap経路・副作用なし（trap時）のケースがある。
- Full VMの既存テストは影響を受けない（別クラス）。
- 観測JSON（§3）がcorpusの期待値として固定されている。
