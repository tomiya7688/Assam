# Assam Core プロファイル

言語: 日本語 | [English](../en/assam-core.md)

状態: Draft

Assam Coreは、Bitlang VMなどの実行ターゲットが使う、ASSAMの厳密な低水準プロファイルです。

**独立した言語ではありません。** Full ASSAMには高水準の便利機能、疑似命令、生成器、デバッガー指示、変換機能などを追加できます。一方、Assam Coreは機械やバックエンドが直接生成・処理できる、安定したアセンブリ境界を目指します。

## 主な利用者

Bitlang VMは、Bitlang VM Assemblyの構文と命令プロファイルの基盤としてAssam Coreを利用します。

```text
Bitlang Low
    -> Bitlang VM Backend
    -> Assam Core / Bitlang VM Assembly
    -> Bitlang VM
    -> x64 / ARM64 / RISC-V architecture translation
```

Bitlang Lowは主要な生成元の一つです。そのためCoreは決定的に生成しやすく、バックエンドに人間向けの高水準ASSAM機能を合成させない設計にします。

## 必須のアーキテクチャ移植性

Assam Coreは、複数の実ISAへ機械的に変換できる小さな共通命令層を意図しています。

初期の必須ターゲットは次のとおりです。

- x64 / x86-64
- ARM64 / AArch64
- RISC-V

これらの対応は主に**JSON変換表**で記述します。必要ならCore命令一つを複数のターゲット命令へ展開できますが、変換が別の高水準コンパイラーにならないよう、Coreの意味は小さく保ちます。

追加ターゲットは限定しません。Assamがあらゆる独自CPUやFPGA向けに公式コードを用意する必要はありません。開発者は互換性のあるJSON対応表を書いて、FPGA向けISA、ソフトコアCPU、実験用プロセッサなどを追加できます。

拡張モデルはデータ駆動です。ターゲットがCoreの操作を表現できれば、開発者が対応表を用意します。コミュニティ製・独自ターゲットは、後に公式サポートへ昇格しない限り、x64 / ARM64 / RISC-Vの必須受け入れ条件には含めません。

## 将来の公式バイトコードターゲット

x64 / ARM64 / RISC-Vの必須変換器が安定した後、次の公式変換経路も提供する予定です。

- WebAssembly (Wasm)
- JVM bytecode

これらは後続フェーズであり、初期のAssam Core安定性・受け入れ条件には含めません。

WasmとJVM bytecodeは通常のネイティブISA向けJSON対応表とは異なります。どちらもスタック指向であり、Wasmには構造化制御フロー、JVM bytecodeには検証器・型スタック・クラス／メソッド構造の制約があります。

```text
Assam Core
    -> ターゲット固有の正規化 / CFG + スタック低下
    -> WasmまたはJVM bytecodeへの対応付け・出力
```

汎用JSON対応データで、単純な算術、比較、変換などの対応を記述しても構いません。一方、単純な表だけでは安全に表現できない構造要件には、ターゲット固有の低下処理を認めます。

これはCoreを複雑化してよいという意味ではありません。Wasm/JVM変換器が単純なCoreプログラムをターゲットモデルへ適応させます。変換器を簡単にするためだけに、Wasm専用・JVM専用の複合命令をCoreへ追加してはいけません。

### WebAssembly

将来のWasm変換器は、少なくとも次を扱います。

- Coreのレジスタ／値の流れからWasm local／operand stackへの変換
- 任意のCore CFGから、有効な構造化Wasm制御フローまたは意味を保つ別形式への低下
- ゲストメモリのlinear memoryへの対応
- call、return、trap、runtime helper
- 選択したAssam/Bitlangプロファイルが要求する決定的な整数幅の意味

### JVM bytecode

将来のJVM bytecode変換器は、少なくとも次を扱います。

- Coreのレジスタ／値の流れからJVM local／operand stackへの変換
- JVM検証器と互換性のあるstack／型状態
- ラベル、分岐、call、return
- JVMオブジェクト参照を生のゲストポインターと見なさず、明示的なruntime表現でゲストメモリを扱うこと
- 生成クラス／メソッド構造とruntime helper境界
- JVM bytecodeに直接ない操作を意味保存的に低下させること

どちらの変換器も、Bitlangのソースレベルの所有権、借用、クラスなどの高水準意味を再構築してはいけません。

## Core設計規則

1. 一命令の低水準効果は明示する。
2. 制御フローは明示する。
3. メモリ効果は明示する。
4. runtime失敗はホスト言語の偶発的動作ではなく、定義済みのtrap／error動作を使う。
5. Coreに暗黙の所有権、cleanup、allocation、動的dispatch、closure captureなどの高水準動作を持ち込まない。
6. 疑似命令や便利構文はFull ASSAMに限り、Coreへ決定的に低下できる場合にのみ認める。
7. Core命令の意味は版管理し、機械可読にする。
8. Parser、VM、変換器は別々のopcode表でなく、同じ正規命令定義を使う。
9. ターゲットISAが一命令で表せないCore操作は、複数のターゲット命令へ対応付けてもよい。
10. 新しいCore命令は、明示されたruntime/VM ABIプリミティブを除き、x64、ARM64、RISC-Vへの対応表を定義できるほど単純であること。
11. アーキテクチャ固有の複雑な意味低下を要する操作は、通常、変換前により単純なCore命令へ分解する。
12. ASSAMインタープリターや特定CPUに都合がよいという理由だけでCore命令を追加しない。

## 命令の単純性ゲート

Assam Coreは機能豊富なアセンブリ言語ではなく、移植可能なmicro-operation／RISC風の層を意図しています。

Core命令への採用審査では、次を確認します。

- 隠れた高水準状態なしにオペランドと効果を記述できるか。
- x64、ARM64、RISC-Vへの対応を、小さなJSON命令列と明示的なオペランド調整で表現できるか。
- すべてのメモリ効果が見えるか。
- すべての制御フロー効果が見えるか。
- 失敗／trap条件が明示されているか。
- 実装にソース言語の概念の再構築が必要にならないか。

対応付けの問いに「いいえ」、または再構築の問いに「はい」となるなら、通常はより小さなCore操作へ低下させます。

高水準の端末／device命令、暗黙のobject操作、複合resource管理、closure操作、言語レベルのallocation方針、複雑な便利命令などは、プリミティブへ分解しない限りCoreの外に置きます。Full ASSAMで公開する場合も、Core変換前に低下させます。

## JSONアーキテクチャ対応契約

アーキテクチャ対応データは機械可読で、版管理される必要があります。

変換テンプレートを定義する前段として、[target-mapping-coverage-v1.schema.json](../../assam/data/target-mapping-coverage-v1.schema.json) に従う網羅マニフェスト形式を定めます。これはターゲット／profileごとに各 `target_mapping_id` の `in_scope` または `out_of_scope` を宣言し、後者には理由を必須とします。`in_scope` は変換列の実装済みを意味しません。このschemaだけではレジストリとの網羅性・重複を検査しません。

`assam check-target-coverage <manifest.json>` はmanifest v1の必須構造を検査した後、同梱Coreレジストリと照合し、全Core hook IDが一度ずつ宣言され、未知IDや重複がないことを検査します。別レジストリを検査する場合は `--registry <registry.json>`、機械処理向けJSON出力には `--format json` を指定します。結果の `validation_scope` は `coverage_declarations_only` であり、変換実装や実行可能性は検査しません。

`assam check-target-matrix <x64.json> <arm64.json> <riscv.json>` は各manifestの網羅宣言を個別に検査したうえで、必須3ターゲット（別名 `x86-64` / `AArch64` / `RISC-V`・`riscv64`）が揃うことを確認します。カスタムターゲットmanifestも追加でき、`--format json` で結果を機械処理できます。結果の `validation_scope` は `coverage_declarations_only` であり、`in_scope` の変換実装や実行可能性は証明しません。

対応表も一括照合する場合は、各対応表に対して `--mapping <mapping.json>` を繰り返し指定します。全manifestに対して同じarchitecture／profileの対応表が一つずつ必要です。ファイルの指定順は問いません。対応表の不足・重複、対応するmanifestのない表、`in_scope` の命令列不足、`out_of_scope` との矛盾を拒否します。追加の独自ターゲットや複数profileにも同じ規則を適用し、`--registry` は全ファイルに共通で使います。JSON結果の `validation_scope` は `mapping_matrix_structure_registry_references_and_coverage_only` となり、`mapping_table_count` とターゲット／profile順の `mappings` に検査結果を含めます。検査するのは命令列の構造と宣言の整合性であり、変換意味や実行結果の同等性は別途検証します。

同梱Draft例は `examples/targets/` のx86-64・AArch64・RV64Iの3組です。AArch64の `a64-draft` は単純なデータ演算と分岐の命令列候補だけを `in_scope` とし、メモリ、除算、シフト、比較結果、呼出／復帰、停止は不足する意味・ABI情報を理由に `out_of_scope` とします。`in_scope` も即値のエンコード、レジスタ割当て、幅、分岐距離や実行結果を保証しません。3組の一括構造照合はCIで行いますが、変換fixtureを通した受け入れ条件は未達です。

`assam scaffold-target-coverage <architecture> <profile>` はCore hook IDをすべて含むJSON雛形を標準出力へ出します。全項目は理由付き `out_of_scope` として生成されるため、各項目をレビューして明示的に分類し直す必要があります。雛形の出力やmatrix検査は対応実装を表明しません。

実対応データの最小構造は [target-mapping-v1.schema.json](../../assam/data/target-mapping-v1.schema.json) でDraft定義します。Core hook IDごとに、ターゲットopcodeと、Core operand参照・即値・ターゲットレジスタ・scratch名・symbolからなる命令列を記述できます。このschemaはJSON形状だけを検査し、命令意味の同等性、レジスタ割当て、制約、分岐条件、幅／符号variant、ABI helper、Core registryとの網羅性は検証しません。したがって実行可能な変換契約ではなく、coverage manifestの `in_scope` 宣言も実装済みを意味しません。

`assam check-target-mappings <mapping.json>` はこの構造とCore registry上のhook ID参照・重複を検査します。`core_operand.index` は0始まりで、対応するCore命令のオペランド数未満でなければなりません。`--registry` で別registryを指定した場合も、その定義で参照範囲を検査します。`--format json` の結果には `validation_scope: "mapping_structure_and_registry_references_only"` を含めます。未記載のCore hookはJSONでは一覧、テキストでは件数として報告しますが、このコマンドも変換意味や実行可能性は検証しません。

`assam check-target-mappings <mapping.json> --coverage <manifest.json>` は、同じregistryを使ってmanifest全体も検査し、mapping表のhook集合が `in_scope` 宣言と一致することを確認します。`in_scope` の命令列不足と `out_of_scope` のhookに対する命令列をエラーにします。両ファイルのarchitectureはmatrix検査と同じ別名規則で比較し、profileは文字列が完全一致する必要があります。JSON結果の `validation_scope` は `mapping_structure_registry_references_and_coverage_only` となり、`coverage` に宣言の検査結果を含めます。これは命令列の存在と参照の整合性を確認するもので、変換意味や実行結果の同等性は引き続き別途検証が必要です。

各ターゲット対応表は最低限、次を表現できる必要があります。

- Core opcode／profileの版
- ターゲットのアーキテクチャ／profile
- オペランド対応と制約
- 1対1または1対多のターゲット命令テンプレート
- 即値／レジスタの制限
- 宣言的に表現可能な場合の一時／scratch resource要件
- condition codeまたはbranch条件の対応
- 幅／符号のvariant
- 事前のCore分解が必要な非対応組み合わせ
- 定義済みruntime境界で必要なターゲットABI／helper call ID

対応表に汎用プログラミング言語を埋め込んではいけません。複雑な意味処理が必要なら、先にCoreを単純化・分解します。

### 独自／FPGAターゲットの拡張

汎用対応システムでは、Assam Coreを変更せずに開発者が追加ターゲット表を作成できる必要があります。

たとえばFPGA開発者は、Core操作を独自ISAへ直接どう対応させるかを記したJSONを用意できます。利用だけのために、そのターゲットを上流へ取り込んだり、専用組み込みmoduleを実装したりする必要はありません。

独自対応表は、ターゲット／profileの識別情報と対応範囲を宣言します。未対応のCore操作は、黙って近似せず明示的に診断します。

## Bitlang Lowから引き継ぐ要件

Assam Coreは、Bitlang Low backendが次を保持できる必要があります。

- 任意の意味的な整数幅と符号（直接、または明示的な低下列で対応）
- Bitlangの`Int<Radix>x*` / `Uint<Radix>x*`は任意精度整数として意味を保ち、必要なら動的limb／runtime helperへ明示的に低下させること。固定幅レジスタ、架空の有限幅、切り詰めで代用してはいけません。数値型の`x0`は無効であり、`x*`の別名ではありません。意味論が定義されるまでは`Float<Radix>x*`を拒否し、host floatへ代用してはいけません。
- zero-payload値は意味上の有効性と物理格納サイズを区別すること。ゼロ長配列は要素数0、N個のゼロpayload要素を持つ配列はN個の論理要素と通常のbounds検査を保ちます。物理strideが0でもアドレス算術を論理indexの代わりにせず、identity／Ref／borrow／lifetimeが観測可能なら保持します。不要なheap割当てや一意な物理アドレスを仮定せず、必要なdescriptor／helperは明示します。
- checked overflow動作
- shift数を検証した決定的な論理／算術shift
- 比較と明示的な条件／無条件branch
- function call／returnと明示的な呼出規約
- byte-addressable、または厳密に定義されたmemory access
- bounds check／trap列
- 決定的なLoad/Store幅とendian
- 一命令で表せない意味処理のための明示的helper call

Bitlangの所有権、借用、Ref、cleanup、class、closureの意味検証・低下はCoreより前に済ませます。Coreはその結果としての明示的な操作と制御フローを実行し、高水準解析を再実装しません。

これらの型意味論はAssam独自に再定義せず、Bitlang Lowの[数値型](https://github.com/tomiya7688/Bitlang_low/blob/main/docs/numeric-types.md)、[言語仕様](https://github.com/tomiya7688/Bitlang_low/blob/main/docs/language-spec.md)、[exact layout](https://github.com/tomiya7688/Bitlang_low/blob/main/docs/exact-layout.md)、[runtime helper ABI](https://github.com/tomiya7688/Bitlang_low/blob/main/docs/runtime-helper-abi.md)を参照します。ここでの要件はCore opcode追加ではなく、backend loweringと明示的ABIの制約です。

## 構文の基準

既存のASSAMテキスト形式を出発点とします。

- labelは分岐／call先を識別する。
- 命令はopcodeと明示的オペランドからなる。
- register、immediate、symbolを字句上区別できる。
- commentと空白は意味を持たない。
- Parserが互換aliasを受け付けても、生成器は正規表記を出力する。

profileが安定する前に、正確な文法、オペランド種別、opcode集合、profile／版marker、エラー規則を形式化します。

Pythonリファレンス実装の `core` 検証profileは、VM専用の便利命令 `Push` / `Pop` と高水準端末操作を除外します。版管理された [JSONレジストリ](../../assam/data/instruction_registry.json) は、opcode alias、オペランドrole、実行handler識別子、レジスタread/write位置、ゲストデータメモリ効果、整数parameter位置、命令固有trap条件、ターゲット対応hook ID、制御フロー分類の共通定義です。Parser、C translator、VM、analyzerがこれを参照します。v2形式は [instruction-registry-v2.schema.json](../../assam/data/instruction-registry-v2.schema.json) で定義します。Core各opcodeの `target_mapping_id` は将来の宣言的対応表向けの名前であり、対応表やターゲット網羅性が存在することを意味しません。ゲストデータメモリ効果はVM内部stackや端末bus効果と別です。整数幅と符号は明示的に `not_decided` とし、未決事項を記録するだけで実行意味は定めません。trap条件は現在のPythonリファレンスVMで観測された動作であり、Draft Coreの規範的意味ではありません。ホスト／環境エラーは含めません。Schemaの版がCoreの安定性を示すわけではありません。オペランド意味、ABI、ターゲット対応が仕様化・検証されるまでprofileはDraftです。

JSON IRは、profile名、profile版、命令レジストリschema版を含む任意の `profile` markerを持てます。`assam json --profile core` は検証してmarkerを付与します。JSON契約は [program-ir-v1.schema.json](../../assam/data/program-ir-v1.schema.json)、marker単体のschemaは [assam-core-profile-draft.schema.json](../../assam/data/assam-core-profile-draft.schema.json) で定義します。markerのない従来JSONは引き続き有効で、既定でFullとして扱います。現在のCore版文字列は `draft` で、互換性を示すためのものであり、安定版の保証ではありません。

## アーキテクチャ変換の受け入れ条件

次を満たすまでAssam Coreを安定版とは見なしません。

- x64対応JSONがあり、変換fixtureを通過する。
- ARM64対応JSONがあり、変換fixtureを通過する。
- RISC-V対応JSONがあり、変換fixtureを通過する。
- 通常のCore opcodeすべてに3アーキテクチャの対応があるか、runtime／VM ABI primitiveとして明示分類されている。
- CI／schema検証で、対応漏れの通常Core opcodeを拒否する。
- ターゲット実行・テスト環境が利用できる場合、代表的プログラムがリファレンスVMと変換先で同等の結果になる。

## 互換性規則

有効なAssam Coreプログラムは、対応する言語版のASSAMプログラムとしても有効でなければなりません。

逆は必須ではありません。Full ASSAMはBitlang VMでは意図的に利用できない機能を持つことがあります。
