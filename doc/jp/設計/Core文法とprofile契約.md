# Core文法とprofile契約

言語: 日本語 | [English](../../en/design/core-grammar-and-profile.md)

対象Issue: #1（文法・profile/version）、#10（operand型・文字列の保存）。決定: DEC-01, DEC-11, DEC-17、PRO-01, PRO-02。

## 1. 二つの入口と一つのIR

```text
Full text  --(Full parser)------\
                                 +--> Program(IR, 型付きoperand) --> 検証(profile別) --> VM / 変換
Core text  --(Core parser)------/
JSON IR ---(loader)------------/
```

- **Full parser**: 現行の自由な構文（PascalCase・case-insensitive・空白/カンマ・alias・引用文字列）を後方互換で受理する。
- **Core parser**: canonical形のみを受理する厳格なparser。**別クラス・別ファイル**にする。Full parserを緩めたり再利用して分岐したりしない。
- 両者は同じ`Program`（型付きoperand）を作る。以降の検証・実行・変換はIRを入力とし、textの形に依存しない。

## 2. 型付きoperand（#10）

現行はoperandが「文字列/整数」で、`"r1"`が文字列かレジスタか区別できない。これを次の4種に分ける。

| kind        | 例（text）          | IR表現                            | 備考                                                  |
| ----------- | ------------------- | --------------------------------- | ----------------------------------------------------- |
| `register`  | `r5`                | `{"kind":"register","index":5}`   | Coreは`r0`〜`r31`。Fullも`r0`〜`r31`へ広げる（WP-B1） |
| `immediate` | `42`, `0x2A`, `-1`  | `{"kind":"immediate","value":42}` | 10進/`0x`。符号付き。範囲は命令ごと（意味論参照）     |
| `symbol`    | `loop`（label参照） | `{"kind":"symbol","name":"loop"}` | label / 変換先ABI helper名                            |
| `string`    | `"a;b"`             | `{"kind":"string","value":"a;b"}` | **Fullのみ**。Coreでは拒否                            |

### 2.1 IR schema v2

- `program-ir-v2.schema.json`を追加し、operandを上記のtagged objectで表す。
- **v1の読み込み互換**: v1（operandが生の文字列/整数）は読み込み時に次で型付きへ正規化する。整数→`immediate`、`r`+数字（範囲内）→`register`、ラベル表に存在する名前→`symbol`、それ以外の文字列→`symbol`（命令がsymbolを許す位置）または`string`（Fullで`string`を許す位置）。曖昧な場合は**拒否**する（黙った推測をしない）。
- v1出力は維持しない。generatorは新規出力をv2にする。`json --legacy-v1`のような互換出力は作らない（v1を受理するだけ）。
- Core profile印と同様に、IRは`schema_version`を持つ。

### 2.2 文字列literal（#10の受け入れ条件）

Full parserは次を満たす。

1. commentの`;`は、引用符・エスケープ状態を追跡して判定する。引用内の`;`と`#`はliteralとして保存する。
2. 引用operandは常に`string`として保存し、内容が数値風（`"123"`）やレジスタ風（`"r1"`）でも変換しない。
3. 空文字列`""`を保存できる。
4. エスケープは`\"`・`\\`・`\n`・`\t`・`\r`・`\xHH`, `\uHHHH`。未定義のエスケープと閉じ忘れは診断エラー。
5. VMはoperandの`kind`でレジスタ参照と文字列を区別する。`_value`が型で分岐し、文字列を数値/レジスタに再解釈しない。

Coreでは`string` operandを許す命令がない。Coreに文字列処理命令を新設する理由にしない（DEC-17）。

## 3. Core canonical text 文法（Core v1）

```ebnf
program     = { line } ;
line        = [ label_def | instruction ] , [ comment ] , newline ;
label_def   = ident , ":" ;
instruction = opcode , [ ws , operand , { ws? , "," , ws? , operand } ] ;
comment     = ";" , { any_char_except_newline } ;
opcode      = lower , { lower | digit | "_" } ;
operand     = register | immediate | ident ;
register    = "r" , ( "0" | nonzero_digit [ digit ] ) ;   (* r0..r31 に制限は検証で行う *)
immediate   = [ "-" ] , ( dec_digits | "0x" , hex_digits ) ;
ident       = ( letter | "_" ) , { letter | digit | "_" } ;
```

規則:

- 1行に命令またはlabel定義のどちらかを1つ。1行に複数命令を書かない。label定義は単独行（命令と同一行にしない）。
- opcodeは小文字・case-sensitive。aliasとPascalCaseはCoreで拒否する。
- operand間は**カンマ必須**。空白だけの区切りは拒否する。カンマ・opcode後の空白は任意。
- 先頭・末尾の空白、空行、コメントだけの行は意味を持たない。タブは空白と同じ。
- identはASCIIのみ。labelの重複と予約語（opcode名・`r0`〜`r31`）との衝突は拒否する。
- レジスタ範囲外（`r32`）、桁あふれ、不正な16進、先頭`+`などは拒否する。
- 命令ごとのoperand数・kindはregistryが固定する。parserはregistryに従い**実行前に**検証する（構文・label・範囲・profile）。
- 行末は`\n`または`\r\n`。BOMは拒否。文字コードはUTF-8。非ASCIIはコメント内のみ許す。

正規化出力（canonical emitter）:

- 1命令`opcode␣op1,␣op2,␣op3`（カンマの後に半角空白1つ、opcode後に半角空白1つ）、インデントはlabel外で4空白、label行は`name:`、行末`\n`、末尾に改行1つ。
- 即値は10進（負数は`-`付き）。`0x`入力は10進へ正規化する（比較しやすさのため）。
- `parse(emit(p)) == p`、`emit(parse(canonical)) == canonical`をgolden testで保証する。

例:

```text
entry:
    const r1, 7
    const r2, 1
loop:
    brz r1, done
    sub r1, r1, r2
    jump loop
done:
    halt
```

## 4. 診断（malformed Core）

診断は安定したコードと位置を持つ。メッセージ文言は変わりうるが、`code`は互換契約とする。

| code                                                                 | 条件                                                        |
| -------------------------------------------------------------------- | ----------------------------------------------------------- |
| `core.syntax.unknown_opcode`                                         | registryにない／別profileのopcode（alias・PascalCase含む）  |
| `core.syntax.operand_count`                                          | operand数が定義と異なる                                     |
| `core.syntax.operand_kind`                                           | operand種別が定義と異なる（例: 即値が必要な位置にレジスタ） |
| `core.syntax.separator`                                              | operand間のカンマ欠落・余分なカンマ                         |
| `core.syntax.register_range`                                         | `r0`〜`r31`の範囲外                                         |
| `core.syntax.immediate_range`                                        | 即値がその命令の許容範囲外                                  |
| `core.syntax.label_dangling`                                         | label定義の後ろに命令がない（IRのlabel表は命令位置を指す）  |
| `core.syntax.label_duplicate` / `label_undefined` / `label_reserved` | label規則違反                                               |
| `core.syntax.line_form`                                              | 1行複数命令、label+命令同一行など                           |
| `core.syntax.encoding`                                               | UTF-8違反、BOM、制御文字                                    |
| `core.profile.disallowed`                                            | Fullの機能（string operand等）をCoreに使用                  |

出力: `{"code", "message", "line", "column", "source_line"}`。複数診断は最大N件（既定20）をまとめて返し、最初の1件で打ち切らない。CLIは非0で終了する。

## 5. Profile / version 契約

- profile名は`full`・`core`、版は`core`のみ`1`（将来`2`以降）。`full`は版を持たない（現行互換）。
- IR印: `{"name":"Assam Core","version":"1","registry_schema_version":3}`。Draftの`"draft"`は読み込み時に**拒否**し、移行手順を診断で案内する（Q4の確定後）。
- 互換（**構文上**）: 有効なCore v`N`プログラムのcanonical textは、Fullのtext parserでもそのまま受理できる（DEC-11の逆は非必須）。そのためFullのレジストリにもCore v`N`の全命令を`availability`で含め（`const`/`trap`/`hcall`等を追加）、Fullのレジスタ範囲を`r0`〜`r31`へ広げる（WP-B1/B3）。これを**Core→Full上位互換テスト**で保証する。
- **意味は互換を主張しない**: Fullは無限精度整数・疎memory等の現行意味を維持するため、同名命令の実行結果がCoreと異なりうる（例: `shl`、`add`の桁あふれ）。意味が異なる同名命令は、registry上でprofile別のエントリ（別`id`）に分ける。実行結果の比較はprofileごとのconformanceで行い、FullでCore programを走らせて同一結果になることは保証しない。
- Fullにだけ存在できるもの: PascalCase/alias、空白区切り、引用文字列、`Push`/`Pop`、端末命令、疑似命令。疑似命令はCoreへ決定的に低下できる場合のみ許し、変換後にCore検証を通す。
- GoのVMは独自文法を持たず、同一版のparser/registryを利用する（共通テスト入力はconformance corpus）。

## 6. 受け入れ条件（WP-B1 / WP-B2）

- #10: `Move r0 "a;b"`→文字列`a;b`、`"123"`→文字列、`"r1"`→文字列。空文字列・引用符/コメント記号を含む文字列の往復（text→IR→JSON→IR→text）テスト。
- #1: 上記文法のparser conformance / golden tests。全診断コードに最低1つの負例。
- Core→Full上位互換テスト、Fullの既存テストが全て通ること。
- Go VMが同一のregistryとcorpusで同じ受理/拒否になること（Go側は別リポジトリ。corpusは本リポジトリから配布）。
